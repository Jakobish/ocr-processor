"""Recover expired worker leases and enforce data retention."""
import argparse
import signal
import threading


def main():
    from enterprise.settings import EnterpriseSettings
    from enterprise.database import Database
    from enterprise.progress import DurableProgressTracker
    from logger import log_manager
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    settings = EnterpriseSettings.from_env()
    tracker = DurableProgressTracker(Database(settings.database_url), settings)
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    while not stop.is_set():
        try:
            recovered = tracker.recover()
            cleaned = tracker.cleanup()
            log_manager.logger.info('Maintenance completed', event_type='maintenance_complete', recovered=recovered, cleaned=cleaned)
        except Exception:
            if args.once:
                raise
            log_manager.logger.error('Maintenance failed', event_type='maintenance_failed')
        if args.once:
            return
        stop.wait(settings.maintenance_interval)


if __name__ == '__main__':
    main()
