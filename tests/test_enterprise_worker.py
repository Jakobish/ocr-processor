"""Worker lifecycle tests: leases, process cancellation and publication fencing."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import tempfile
import unittest

from enterprise.worker import Worker


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.output = root / 'attempt'
        self.output.mkdir()
        self.storage = Mock()
        self.storage.attempt_dir.return_value = ('tenant/attempt', self.output)
        self.storage.path.return_value = root / 'source.pdf'
        self.settings = SimpleNamespace(timeout_seconds=10, heartbeat_seconds=.01)
        self.tracker = Mock()
        self.tracker.heartbeat.return_value = True
        self.tracker.cancelled.return_value = False
        self.claim = SimpleNamespace(job_id='j', attempt_id='a', lease_token='l', tenant_id='t', source_key='source', filename='test.pdf', mode='cli', language='heb+eng')
        self.tracker.claim.return_value = self.claim
        self.process = Mock(pid=123456)
        self.process.poll.return_value = 0
        self.worker = Worker(self.tracker, self.storage, self.settings, process_factory=Mock(return_value=self.process))

    def artifacts(self):
        for name in ('ocr_output.pdf', 'ocr_output.txt', 'ocr_log.txt'):
            (self.output / name).write_text('test')

    def test_success_publishes_artifacts_with_lease(self):
        self.artifacts()
        self.assertTrue(self.worker.run_once())
        self.tracker.complete.assert_called_once_with('j', 'l', {'pdf': 'tenant/attempt/ocr_output.pdf', 'text': 'tenant/attempt/ocr_output.txt', 'log': 'tenant/attempt/ocr_log.txt'})
        self.assertTrue(self.worker.process_factory.call_args.kwargs['start_new_session'])

    def test_missing_outputs_never_published(self):
        self.worker.run_once()
        self.tracker.complete.assert_not_called()
        self.assertEqual(self.tracker.fail.call_args.args[2], 'invalid_output')

    def test_cancelled_before_publication_is_not_success(self):
        self.artifacts()
        self.tracker.heartbeat.return_value = False
        self.tracker.cancelled.return_value = True
        self.worker.run_once()
        self.tracker.complete.assert_not_called()
        self.tracker.finish_cancel.assert_called_once_with('j', 'l')

    def test_permanent_failure_does_not_retry(self):
        self.process.poll.return_value = 2
        self.worker.run_once()
        self.assertFalse(self.tracker.fail.call_args.kwargs['retryable'])

    def test_temporary_failure_retries(self):
        self.process.poll.return_value = 1
        self.worker.run_once()
        self.assertTrue(self.tracker.fail.call_args.kwargs['retryable'])

    def test_no_claim_does_not_start_child(self):
        self.tracker.claim.return_value = None
        self.assertFalse(self.worker.run_once())
        self.worker.process_factory.assert_not_called()

    def test_timeout_stops_process_before_recording_failure(self):
        self.settings.timeout_seconds = 0
        self.process.poll.return_value = None
        self.worker.terminate = Mock()
        self.worker.run_once()
        self.worker.terminate.assert_called_once_with(self.process)
        self.assertEqual(self.tracker.fail.call_args.args[2], 'timeout')

    def test_lease_loss_stops_process_without_publishing(self):
        self.tracker.heartbeat.return_value = False
        self.worker.terminate = Mock()
        self.worker.run_once()
        self.worker.terminate.assert_called_once_with(self.process)
        self.tracker.complete.assert_not_called()
        self.tracker.fail.assert_not_called()
        self.tracker.finish_cancel.assert_not_called()

    def test_shutdown_preserves_retryable_work(self):
        self.worker.stop.set()
        self.worker.terminate = Mock()
        self.worker.run_once()
        self.worker.terminate.assert_called_once_with(self.process)
        self.assertEqual(self.tracker.fail.call_args.args[2], 'worker_shutdown')

    @unittest.skipUnless(__import__('os').name == 'posix', 'POSIX process groups')
    def test_terminate_kills_real_process_group(self):
        import os
        import subprocess
        import sys
        import time
        pidfile = Path(self.tmp.name) / 'child.pid'
        script = ("import subprocess,sys,time; "
                  "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
                  "open(sys.argv[1],'w').write(str(p.pid)); time.sleep(60)")
        process = subprocess.Popen([sys.executable, '-c', script, str(pidfile)], start_new_session=True)
        try:
            deadline = time.monotonic() + 5
            while not pidfile.exists() and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertTrue(pidfile.exists())
            child_pid = int(pidfile.read_text())
            Worker.terminate(process)
            self.assertIsNotNone(process.poll())
            import psutil
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if not psutil.pid_exists(child_pid):
                    break
                if psutil.Process(child_pid).status() == psutil.STATUS_ZOMBIE:
                    break
                time.sleep(.02)
            else:
                self.fail('OCR descendant survived process-group termination')
        finally:
            if process.poll() is None:
                Worker.terminate(process)


class WorkerTrackerIntegrationTests(unittest.TestCase):
    def setUp(self):
        from enterprise.database import Base, Database
        from enterprise.identity import Principal
        from enterprise.progress import DurableProgressTracker
        from enterprise.settings import EnterpriseSettings
        from enterprise.storage import LocalStorage
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.settings = EnterpriseSettings(database_url=f'sqlite:///{self.tmp.name}/jobs.db', storage_root=Path(self.tmp.name)/'storage')
        self.db = Database(self.settings.database_url)
        self.addCleanup(self.db.engine.dispose)
        Base.metadata.create_all(self.db.engine)
        self.storage = LocalStorage(self.settings.storage_root)
        self.tracker = DurableProgressTracker(self.db, self.settings)
        self.principal = Principal('user', 'team', 'member')
        key = self.storage.upload_key('team')
        self.storage.path(key).parent.mkdir(parents=True, exist_ok=True)
        self.storage.path(key).write_bytes(b'%PDF-test fixture')
        upload = self.tracker.register_upload(self.principal, 'document.pdf', key, 17)
        batch = self.tracker.create_batch(self.principal, [upload['id']], 'cli', 'eng', 'submission')
        self.job_id = batch['jobs'][0]['id']

    def process(self, command, **options):
        output = Path(command[command.index('--output') + 1])
        for name in ('ocr_output.pdf', 'ocr_output.txt', 'ocr_log.txt'):
            (output / name).write_text('Valid runner output')
        return Mock(pid=999999, poll=Mock(return_value=0))

    def test_worker_publishes_to_real_tracker_and_new_tracker_reads_result(self):
        from enterprise.progress import DurableProgressTracker
        worker = Worker(self.tracker, self.storage, self.settings, process_factory=self.process)
        worker.run_once()
        fresh = DurableProgressTracker(self.db, self.settings)
        job = fresh.get_job(self.principal, self.job_id)
        self.assertEqual(job['status'], 'completed')
        self.assertEqual(job['attempt_count'], 1)
        self.assertEqual({item['kind'] for item in job['artifacts']}, {'pdf', 'text', 'log'})
        self.assertTrue(fresh.artifact(self.principal, self.job_id, 'pdf').is_file())
        self.assertFalse(worker.run_once())

    def test_cancel_after_claim_prevents_publication(self):
        def cancelled_process(command, **options):
            process = self.process(command, **options)
            self.tracker.cancel(self.principal, self.job_id)
            return process
        worker = Worker(self.tracker, self.storage, self.settings, process_factory=cancelled_process)
        worker.terminate = Mock()
        worker.run_once()
        self.assertEqual(self.tracker.get_job(self.principal, self.job_id)['status'], 'cancelled')
        self.assertIsNone(self.tracker.artifact(self.principal, self.job_id, 'pdf'))

    def test_recovered_lease_cannot_publish_stale_worker_outputs(self):
        from datetime import timedelta
        from enterprise.database import Job, utcnow
        def lost_process(command, **options):
            process = self.process(command, **options)
            with self.db.session() as session:
                session.get(Job, self.job_id).lease_until = utcnow() - timedelta(seconds=1)
            self.assertEqual(self.tracker.recover(), 1)
            return process
        worker = Worker(self.tracker, self.storage, self.settings, process_factory=lost_process)
        worker.terminate = Mock()
        worker.run_once()
        self.assertEqual(self.tracker.get_job(self.principal, self.job_id)['status'], 'retry_wait')
        self.assertIsNone(self.tracker.artifact(self.principal, self.job_id, 'pdf'))
