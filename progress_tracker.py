"""
Enterprise OCR Progress Tracking and Metrics Collection
Provides real-time progress tracking, performance metrics, and job management
"""
import time
import threading
import uuid
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
from pathlib import Path
import psutil
import os
from logger import log_manager


class JobStatus(Enum):
    """Job status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class JobPriority(Enum):
    """Job priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class Job:
    """OCR processing job"""
    job_id: str
    input_path: str
    mode: str
    language: str = "heb+eng"
    priority: JobPriority = JobPriority.NORMAL
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0
    current_file: str = ""
    total_files: int = 0
    processed_files: int = 0
    failed_files: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None


@dataclass
class PerformanceMetrics:
    """Performance metrics collection"""
    total_processing_time: float = 0.0
    average_file_time: float = 0.0
    files_per_minute: float = 0.0
    memory_usage_peak: float = 0.0
    cpu_usage_average: float = 0.0
    error_rate: float = 0.0
    throughput_mb_per_minute: float = 0.0
    total_files_processed: int = 0
    total_data_processed_mb: float = 0.0


@dataclass
class SystemMetrics:
    """System resource metrics"""
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_usage_percent: float = 0.0
    network_io: Dict[str, int] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class MetricsCollector:
    """Collect and aggregate performance metrics"""

    def __init__(self):
        self.metrics = PerformanceMetrics()
        self.system_metrics_history: List[SystemMetrics] = []
        self.max_history_size = 1000
        self._lock = threading.Lock()

    def record_job_completion(self, job: Job, processing_time: float, file_size_mb: float):
        """Record metrics for completed job"""
        with self._lock:
            self.metrics.total_files_processed += job.processed_files
            self.metrics.total_data_processed_mb += file_size_mb
            self.metrics.total_processing_time += processing_time

            if self.metrics.total_files_processed > 0:
                self.metrics.average_file_time = (
                    self.metrics.total_processing_time / self.metrics.total_files_processed
                )
                self.metrics.files_per_minute = (
                    self.metrics.total_files_processed / (self.metrics.total_processing_time / 60)
                )

            if self.metrics.total_data_processed_mb > 0:
                self.metrics.throughput_mb_per_minute = (
                    self.metrics.total_data_processed_mb / (self.metrics.total_processing_time / 60)
                )

            error_rate = job.failed_files / max(job.total_files, 1)
            self.metrics.error_rate = (
                (self.metrics.error_rate * (self.metrics.total_files_processed - job.total_files)) +
                (error_rate * job.total_files)
            ) / self.metrics.total_files_processed

    def record_system_metrics(self):
        """Record current system metrics"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            metrics = SystemMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                disk_usage_percent=disk.percent
            )

            with self._lock:
                self.system_metrics_history.append(metrics)

                # Update peak metrics
                if memory.percent > self.metrics.memory_usage_peak:
                    self.metrics.memory_usage_peak = memory.percent

                # Update average CPU
                if self.system_metrics_history:
                    cpu_values = [m.cpu_percent for m in self.system_metrics_history[-100:]]
                    self.metrics.cpu_usage_average = sum(cpu_values) / len(cpu_values)

                # Maintain history size
                if len(self.system_metrics_history) > self.max_history_size:
                    self.system_metrics_history = self.system_metrics_history[-self.max_history_size:]

        except Exception as e:
            log_manager.logger.warning("Failed to collect system metrics", error=str(e))

    def get_metrics_report(self) -> Dict[str, Any]:
        """Generate comprehensive metrics report"""
        with self._lock:
            return {
                'performance': {
                    'total_processing_time': self.metrics.total_processing_time,
                    'average_file_time': self.metrics.average_file_time,
                    'files_per_minute': self.metrics.files_per_minute,
                    'throughput_mb_per_minute': self.metrics.throughput_mb_per_minute,
                    'total_files_processed': self.metrics.total_files_processed,
                    'total_data_processed_mb': self.metrics.total_data_processed_mb,
                    'error_rate': self.metrics.error_rate,
                    'memory_usage_peak': self.metrics.memory_usage_peak,
                    'cpu_usage_average': self.metrics.cpu_usage_average
                },
                'system': {
                    'current_cpu_percent': psutil.cpu_percent() if psutil else 0,
                    'current_memory_percent': psutil.virtual_memory().percent if psutil else 0,
                    'current_disk_percent': psutil.disk_usage('/').percent if psutil else 0,
                    'history_size': len(self.system_metrics_history)
                },
                'timestamp': datetime.now().isoformat()
            }


class ProgressTracker:
    """Real-time progress tracking for OCR operations"""

    def __init__(self):
        self.jobs: Dict[str, Job] = {}
        self.metrics_collector = MetricsCollector()
        self.active_jobs: Dict[str, threading.Thread] = {}
        self.job_callbacks: Dict[str, List[Callable]] = {}
        self._lock = threading.Lock()

        # Start metrics collection thread
        self._start_metrics_collection()

    def _start_metrics_collection(self):
        """Start background metrics collection"""
        def collect_metrics():
            while True:
                try:
                    self.metrics_collector.record_system_metrics()
                    time.sleep(30)  # Collect every 30 seconds
                except Exception as e:
                    log_manager.logger.error("Metrics collection error", error=str(e))
                    time.sleep(60)

        metrics_thread = threading.Thread(target=collect_metrics, daemon=True)
        metrics_thread.start()

    def create_job(self, input_path: str, mode: str, language: str = "heb+eng",
                  priority: JobPriority = JobPriority.NORMAL, **metadata) -> str:
        """Create a new OCR processing job"""
        job_id = str(uuid.uuid4())

        job = Job(
            job_id=job_id,
            input_path=input_path,
            mode=mode,
            language=language,
            priority=priority,
            metadata=metadata
        )

        with self._lock:
            self.jobs[job_id] = job

        log_manager.logger.info(
            "Job created",
            job_id=job_id,
            input_path=input_path,
            mode=mode,
            priority=priority.value
        )

        return job_id

    def start_job(self, job_id: str) -> bool:
        """Start job execution"""
        with self._lock:
            if job_id not in self.jobs:
                return False

            job = self.jobs[job_id]
            if job.status != JobStatus.PENDING:
                return False

            job.status = JobStatus.RUNNING
            job.started_at = datetime.now()

        log_manager.logger.info(
            "Job started",
            job_id=job_id,
            input_path=job.input_path,
            mode=job.mode
        )

        return True

    def update_progress(self, job_id: str, progress: float, current_file: str = "",
                       processed_files: int = 0, failed_files: int = 0):
        """Update job progress"""
        with self._lock:
            if job_id not in self.jobs:
                return

            job = self.jobs[job_id]
            job.progress = progress
            job.current_file = current_file
            job.processed_files = processed_files
            job.failed_files = failed_files

        # Trigger callbacks
        self._trigger_callbacks(job_id, 'progress', {
            'progress': progress,
            'current_file': current_file,
            'processed_files': processed_files,
            'failed_files': failed_files
        })

    def complete_job(self, job_id: str, success: bool = True, error_message: Optional[str] = None):
        """Mark job as completed"""
        with self._lock:
            if job_id not in self.jobs:
                return

            job = self.jobs[job_id]
            job.status = JobStatus.COMPLETED if success else JobStatus.FAILED
            job.completed_at = datetime.now()
            job.error_message = error_message

            # Calculate processing time
            if job.started_at:
                processing_time = (job.completed_at - job.started_at).total_seconds()
            else:
                processing_time = 0.0

            # Record metrics
            self.metrics_collector.record_job_completion(job, processing_time, 0)  # TODO: Add file size

        status = "completed" if success else "failed"
        log_manager.logger.info(
            "Job finished",
            job_id=job_id,
            status=status,
            processing_time=processing_time,
            total_files=job.total_files,
            processed_files=job.processed_files,
            failed_files=job.failed_files,
            error_message=error_message
        )

        # Trigger callbacks
        self._trigger_callbacks(job_id, 'complete', {
            'success': success,
            'processing_time': processing_time,
            'error_message': error_message
        })

    def cancel_job(self, job_id: str):
        """Cancel a running job"""
        with self._lock:
            if job_id not in self.jobs:
                return

            job = self.jobs[job_id]
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.now()

        log_manager.logger.info("Job cancelled", job_id=job_id)

        self._trigger_callbacks(job_id, 'cancel', {})

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get current job status"""
        with self._lock:
            if job_id not in self.jobs:
                return None

            job = self.jobs[job_id]
            return {
                'job_id': job.job_id,
                'status': job.status.value,
                'progress': job.progress,
                'current_file': job.current_file,
                'total_files': job.total_files,
                'processed_files': job.processed_files,
                'failed_files': job.failed_files,
                'created_at': job.created_at.isoformat(),
                'started_at': job.started_at.isoformat() if job.started_at else None,
                'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                'metadata': job.metadata
            }

    def get_all_jobs(self) -> Dict[str, Dict[str, Any]]:
        """Get all jobs with their status"""
        with self._lock:
            return {
                job_id: {
                    'job_id': job.job_id,
                    'status': job.status.value,
                    'progress': job.progress,
                    'created_at': job.created_at.isoformat(),
                    'mode': job.mode,
                    'input_path': job.input_path
                }
                for job_id, job in self.jobs.items()
            }

    def get_queue_status(self) -> Dict[str, Any]:
        """Get overall queue status"""
        with self._lock:
            jobs_by_status = {}
            for job in self.jobs.values():
                status = job.status.value
                jobs_by_status[status] = jobs_by_status.get(status, 0) + 1

            return {
                'total_jobs': len(self.jobs),
                'jobs_by_status': jobs_by_status,
                'active_jobs': len([j for j in self.jobs.values() if j.status == JobStatus.RUNNING])
            }

    def add_progress_callback(self, job_id: str, callback: Callable):
        """Add callback for job progress updates"""
        with self._lock:
            if job_id not in self.job_callbacks:
                self.job_callbacks[job_id] = []
            self.job_callbacks[job_id].append(callback)

    def remove_progress_callback(self, job_id: str, callback: Callable):
        """Remove progress callback"""
        with self._lock:
            if job_id in self.job_callbacks:
                try:
                    self.job_callbacks[job_id].remove(callback)
                except ValueError:
                    pass

    def _trigger_callbacks(self, job_id: str, event_type: str, data: Dict[str, Any]):
        """Trigger registered callbacks"""
        with self._lock:
            if job_id in self.job_callbacks:
                for callback in self.job_callbacks[job_id]:
                    try:
                        callback(job_id, event_type, data)
                    except Exception as e:
                        log_manager.logger.error(
                            "Progress callback error",
                            job_id=job_id,
                            error=str(e)
                        )

    def export_metrics(self, output_path: Optional[str] = None) -> str:
        """Export metrics to JSON file"""
        report = self.metrics_collector.get_metrics_report()
        report['jobs'] = self.get_all_jobs()
        report['queue_status'] = self.get_queue_status()

        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"ocr_metrics_{timestamp}.json"

        output_path = Path(output_path)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)

        log_manager.logger.info(
            "Metrics exported",
            output_path=str(output_path),
            event_type="metrics_export"
        )

        return str(output_path)

    def cleanup_completed_jobs(self, older_than_days: int = 7):
        """Clean up old completed jobs"""
        cutoff_date = datetime.now() - timedelta(days=older_than_days)

        with self._lock:
            jobs_to_remove = [
                job_id for job_id, job in self.jobs.items()
                if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]
                and job.completed_at
                and job.completed_at < cutoff_date
            ]

            for job_id in jobs_to_remove:
                del self.jobs[job_id]
                if job_id in self.job_callbacks:
                    del self.job_callbacks[job_id]

        if jobs_to_remove:
            log_manager.logger.info(
                "Cleaned up old jobs",
                removed_count=len(jobs_to_remove),
                event_type="job_cleanup"
            )


class ProgressReporter:
    """Real-time progress reporting for console/GUI"""

    def __init__(self, progress_tracker: ProgressTracker):
        self.tracker = progress_tracker
        self.show_system_metrics = True

    def print_job_progress(self, job_id: str):
        """Print current job progress"""
        status = self.tracker.get_job_status(job_id)
        if not status:
            return

        progress_bar = self._create_progress_bar(status['progress'])
        print(f"\r🔄 {status['current_file']} {progress_bar} {status['progress']:.1f}%")
        print(f"   📊 Processed: {status['processed_files']}/{status['total_files']} files")

        if self.show_system_metrics:
            self._print_system_metrics()

    def print_queue_status(self):
        """Print overall queue status"""
        queue_status = self.tracker.get_queue_status()

        print("\n📋 Queue Status:")
        print(f"   Total Jobs: {queue_status['total_jobs']}")
        print(f"   Active Jobs: {queue_status['active_jobs']}")

        for status, count in queue_status['jobs_by_status'].items():
            emoji = {"pending": "⏳", "running": "🔄", "completed": "✅",
                    "failed": "❌", "cancelled": "🚫", "paused": "⏸️"}.get(status, "❓")
            print(f"   {emoji} {status.title()}: {count}")

    def _create_progress_bar(self, progress: float, width: int = 30) -> str:
        """Create visual progress bar"""
        filled = int(width * progress / 100)
        bar = "█" * filled + "░" * (width - filled)
        return f"[{bar}]"

    def _print_system_metrics(self):
        """Print current system metrics"""
        try:
            if psutil:
                cpu = psutil.cpu_percent()
                memory = psutil.virtual_memory()
                print(f"   💻 CPU: {cpu:.1f}% | 💾 RAM: {memory.percent:.1f}%")
        except:
            pass

    def start_real_time_monitoring(self, job_id: str, update_interval: float = 2.0):
        """Start real-time progress monitoring"""
        def monitor():
            last_update = 0
            while True:
                try:
                    status = self.tracker.get_job_status(job_id)
                    if not status or status['status'] in ['completed', 'failed', 'cancelled']:
                        break

                    current_time = time.time()
                    if current_time - last_update >= update_interval:
                        self.print_job_progress(job_id)
                        last_update = current_time

                    time.sleep(0.5)

                except KeyboardInterrupt:
                    break
                except Exception as e:
                    log_manager.logger.error("Monitoring error", error=str(e))
                    time.sleep(1)

        monitor_thread = threading.Thread(target=monitor, daemon=True)
        monitor_thread.start()
        return monitor_thread


# Global progress tracker instance
progress_tracker = ProgressTracker()