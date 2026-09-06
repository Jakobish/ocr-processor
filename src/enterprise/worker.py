"""Lease-aware worker. OCR runs in an isolated, cancellable process group."""
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading
import time
import uuid


class Worker:
    def __init__(self, tracker, storage, settings, *, process_factory=subprocess.Popen):
        self.tracker, self.storage, self.settings = tracker, storage, settings
        self.process_factory = process_factory
        self.stop = threading.Event()
        self.worker_id = f'{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex}'

    @staticmethod
    def terminate(process):
        """Kill the entire session, even if its leader has already exited."""
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.wait(timeout=5)

    def run_once(self):
        claim = self.tracker.claim(self.worker_id)
        if claim is None:
            return False
        from logger import log_manager
        log_manager.logger.info("Worker claimed document", event_type="worker_claimed", job_id=claim.job_id, tenant_id=claim.tenant_id, attempt_id=claim.attempt_id)
        process = None
        try:
            key, output = self.storage.attempt_dir(claim.tenant_id, claim.job_id, claim.attempt_id, claim.mode, claim.filename)
            command = [sys.executable, '-m', 'enterprise.ocr_runner', '--source', str(self.storage.path(claim.source_key)), '--output', str(output), '--mode', claim.mode, '--language', claim.language]
            # Raw OCR console output may contain document text. The runner emits a
            # separate safe artifact log; never retain raw child stdout/stderr.
            process = self.process_factory(command, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            started = time.monotonic()
            while True:
                if self.stop.is_set():
                    self.terminate(process)
                    self.tracker.fail(claim.job_id, claim.lease_token, 'worker_shutdown', 'Worker stopped; processing will retry.', retryable=True)
                    return True
                if not self.tracker.heartbeat(claim.job_id, claim.lease_token):
                    self.terminate(process)
                    if self.tracker.cancelled(claim.job_id, claim.lease_token):
                        self.tracker.finish_cancel(claim.job_id, claim.lease_token)
                    return True
                result = process.poll()
                if result is not None:
                    break
                if time.monotonic() - started >= self.settings.timeout_seconds:
                    self.terminate(process)
                    self.tracker.fail(claim.job_id, claim.lease_token, 'timeout', 'Processing exceeded its time limit.', retryable=True)
                    return True
                self.stop.wait(min(self.settings.heartbeat_seconds, 1))
            if result != 0:
                self.tracker.fail(claim.job_id, claim.lease_token, 'invalid_document' if result == 2 else 'processing_failed', 'Document could not be processed.', retryable=result != 2)
                return True
            names = {'pdf': 'ocr_output.pdf', 'text': 'ocr_output.txt', 'log': 'ocr_log.txt'}
            if not all((output / name).is_file() for name in names.values()) or not (output / names['pdf']).stat().st_size:
                self.tracker.fail(claim.job_id, claim.lease_token, 'invalid_output', 'Required output is missing.', retryable=True)
                return True
            artifacts = {kind: f'{key}/{name}' for kind, name in names.items()}
            if claim.mode == 'force' and output.with_suffix('.zip').is_file():
                artifacts['zip'] = str(Path(key).with_suffix('.zip'))
            published = self.tracker.complete(claim.job_id, claim.lease_token, artifacts)
            log_manager.logger.info("Worker attempt finished", event_type="worker_attempt_finished", job_id=claim.job_id, tenant_id=claim.tenant_id, attempt_id=claim.attempt_id, published=bool(published))
            return True
        except Exception:
            if process is not None:
                self.terminate(process)
            self.tracker.fail(claim.job_id, claim.lease_token, 'worker_error', 'Worker could not finish processing.', retryable=True)
            return True

    def run(self):
        from logger import log_manager
        while not self.stop.is_set():
            try:
                if not self.run_once():
                    self.stop.wait(1)
            except Exception:
                # A DB outage leaves the lease for maintenance to recover.
                log_manager.logger.error('Worker iteration failed', event_type='worker_iteration_failed', worker_id=self.worker_id)
                self.stop.wait(5)


def main():
    from enterprise.settings import EnterpriseSettings
    from enterprise.database import Database
    from enterprise.storage import LocalStorage
    from enterprise.progress import DurableProgressTracker
    settings = EnterpriseSettings.from_env()
    worker = Worker(DurableProgressTracker(Database(settings.database_url), settings), LocalStorage(settings.storage_root), settings)
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: worker.stop.set())
    worker.run()


if __name__ == '__main__':
    main()
