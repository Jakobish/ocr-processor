"""
Enterprise OCR Database Integration
Provides job tracking, audit trails, and persistent storage for enterprise operations
"""
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean, Float, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from sqlalchemy.sql import func
from sqlalchemy.types import TypeDecorator
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
import json
import threading
from contextlib import contextmanager
from pathlib import Path
from logger import log_manager
from config import config


Base = declarative_base()


class JSONType(TypeDecorator):
    """Custom JSON type for SQLAlchemy"""
    impl = Text

    def process_bind_param(self, value, dialect):
        if value is not None:
            return json.dumps(value, default=str)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return {}
        return value


class OCRJob(Base):
    """OCR processing job model"""
    __tablename__ = f"{config.database_table_prefix}jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(64), unique=True, nullable=False, index=True)
    status = Column(String(20), nullable=False, index=True)
    priority = Column(String(20), default='normal')

    # Input details
    input_path = Column(Text, nullable=False)
    input_type = Column(String(20))  # 'file' or 'directory'
    total_files = Column(Integer, default=0)

    # Processing settings
    mode = Column(String(20), nullable=False)
    language = Column(String(50), default='heb+eng')
    recursive = Column(Boolean, default=True)

    # Progress tracking
    progress = Column(Float, default=0.0)
    processed_files = Column(Integer, default=0)
    failed_files = Column(Integer, default=0)

    # Timing
    created_at = Column(DateTime, default=func.now(), nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Results
    output_path = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    processing_time = Column(Float, nullable=True)  # seconds

    # Metadata
    metadata = Column(JSONType, default=dict)

    # Relationships
    files = relationship("OCRFile", back_populates="job", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="job", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<OCRJob(job_id='{self.job_id}', status='{self.status}')>"


class OCRFile(Base):
    """Individual file processing record"""
    __tablename__ = f"{config.database_table_prefix}files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey(f'{config.database_table_prefix}jobs.id'), nullable=False)

    file_path = Column(Text, nullable=False)
    file_name = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)  # bytes
    mime_type = Column(String(100), nullable=True)

    status = Column(String(20), nullable=False)  # 'pending', 'processing', 'completed', 'failed'
    processing_time = Column(Float, nullable=True)

    # OCR results
    text_length = Column(Integer, default=0)  # characters in extracted text
    pages_processed = Column(Integer, default=0)
    has_visual_output = Column(Boolean, default=False)

    # Error handling
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)

    # File metadata
    checksum_sha256 = Column(String(64), nullable=True)
    metadata = Column(JSONType, default=dict)

    # Relationship
    job = relationship("OCRJob", back_populates="files")

    def __repr__(self):
        return f"<OCRFile(file_name='{self.file_name}', status='{self.status}')>"


class AuditLog(Base):
    """Audit trail for compliance and tracking"""
    __tablename__ = f"{config.database_table_prefix}audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey(f'{config.database_table_prefix}jobs.id'), nullable=True)

    timestamp = Column(DateTime, default=func.now(), nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)  # 'job_created', 'file_processed', etc.
    severity = Column(String(20), default='info')  # 'debug', 'info', 'warning', 'error', 'critical'

    # Event details
    user_id = Column(String(100), nullable=True)
    session_id = Column(String(100), nullable=True)
    ip_address = Column(String(45), nullable=True)

    # Event data
    message = Column(Text, nullable=False)
    details = Column(JSONType, default=dict)

    # Categorization
    category = Column(String(50), nullable=True, index=True)  # 'security', 'performance', 'business'
    tags = Column(JSONType, default=list)

    # Relationship
    job = relationship("OCRJob", back_populates="audit_logs")

    def __repr__(self):
        return f"<AuditLog(event_type='{self.event_type}', timestamp='{self.timestamp}')>"


class PerformanceMetrics(Base):
    """Performance metrics storage"""
    __tablename__ = f"{config.database_table_prefix}performance_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)

    timestamp = Column(DateTime, default=func.now(), nullable=False, index=True)
    metric_name = Column(String(100), nullable=False, index=True)
    metric_value = Column(Float, nullable=False)
    metric_unit = Column(String(20), nullable=True)

    # Context
    job_id = Column(Integer, ForeignKey(f'{config.database_table_prefix}jobs.id'), nullable=True)
    file_id = Column(Integer, ForeignKey(f'{config.database_table_prefix}files.id'), nullable=True)

    # Additional context
    context = Column(JSONType, default=dict)

    def __repr__(self):
        return f"<PerformanceMetrics(metric_name='{self.metric_name}', value='{self.metric_value}')>"


@dataclass
class DatabaseConfig:
    """Database configuration"""
    url: str
    echo: bool = False
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600


class DatabaseManager:
    """Database connection and session management"""

    def __init__(self, config):
        self.config = config
        self.database_config = DatabaseConfig(
            url=config.database_url,
            echo=config.log_level.upper() == 'DEBUG'
        )

        self.engine = None
        self.SessionLocal = None
        self._lock = threading.Lock()

        if config.enable_database:
            self._initialize_database()

    def _initialize_database(self):
        """Initialize database connection and tables"""
        try:
            self.engine = create_engine(
                self.database_config.url,
                echo=self.database_config.echo,
                pool_size=self.database_config.pool_size,
                max_overflow=self.database_config.max_overflow,
                pool_timeout=self.database_config.pool_timeout,
                pool_recycle=self.database_config.pool_recycle
            )

            # Create tables
            Base.metadata.create_all(bind=self.engine)

            # Create session factory
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

            log_manager.logger.info(
                "Database initialized",
                database_url=self.database_config.url,
                tables_created=len(Base.metadata.tables)
            )

        except Exception as e:
            log_manager.logger.error("Database initialization failed", error=str(e))
            raise

    @contextmanager
    def get_session(self):
        """Get database session with automatic cleanup"""
        if not self.SessionLocal:
            raise RuntimeError("Database not initialized")

        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            log_manager.logger.error("Database session error", error=str(e))
            raise
        finally:
            session.close()

    def create_job_record(self, job_id: str, input_path: str, mode: str,
                         language: str = "heb+eng", **metadata) -> OCRJob:
        """Create new job record in database"""
        job_record = OCRJob(
            job_id=job_id,
            status="pending",
            input_path=input_path,
            input_type="file" if Path(input_path).is_file() else "directory",
            mode=mode,
            language=language,
            metadata=metadata
        )

        with self.get_session() as session:
            session.add(job_record)
            session.flush()  # Get the ID without committing
            session.expunge(job_record)  # Detach from session for return

        log_manager.logger.info(
            "Job record created",
            job_id=job_id,
            input_path=input_path,
            mode=mode
        )

        return job_record

    def update_job_status(self, job_id: str, status: str, **updates):
        """Update job status and other fields"""
        with self.get_session() as session:
            job_record = session.query(OCRJob).filter_by(job_id=job_id).first()
            if not job_record:
                log_manager.logger.warning("Job record not found for update", job_id=job_id)
                return False

            # Update status
            job_record.status = status

            # Update other fields based on status
            if status == "running" and not job_record.started_at:
                job_record.started_at = datetime.now()
            elif status in ["completed", "failed", "cancelled"]:
                job_record.completed_at = datetime.now()
                if job_record.started_at:
                    job_record.processing_time = (
                        datetime.now() - job_record.started_at
                    ).total_seconds()

            # Apply other updates
            for key, value in updates.items():
                if hasattr(job_record, key):
                    setattr(job_record, key, value)

            # Create audit log
            self._create_audit_log(
                session, job_record.id, "job_status_changed",
                f"Job status changed to {status}",
                {"old_status": job_record.status, "new_status": status, **updates}
            )

        log_manager.logger.debug(
            "Job status updated",
            job_id=job_id,
            status=status,
            updates=updates
        )

        return True

    def add_file_record(self, job_id: str, file_path: str, file_size: int,
                       mime_type: str = None) -> Optional[OCRFile]:
        """Add file processing record"""
        try:
            file_record = OCRFile(
                file_path=file_path,
                file_name=Path(file_path).name,
                file_size=file_size,
                mime_type=mime_type,
                status="pending"
            )

            with self.get_session() as session:
                # Get job record
                job_record = session.query(OCRJob).filter_by(job_id=job_id).first()
                if not job_record:
                    return None

                job_record.files.append(file_record)
                job_record.total_files += 1

                # Create audit log
                self._create_audit_log(
                    session, job_record.id, "file_added",
                    f"File added to job: {file_record.file_name}",
                    {"file_path": file_path, "file_size": file_size}
                )

            return file_record

        except Exception as e:
            log_manager.logger.error(
                "Failed to add file record",
                job_id=job_id,
                file_path=file_path,
                error=str(e)
            )
            return None

    def update_file_status(self, job_id: str, file_path: str, status: str,
                          processing_time: float = None, **updates):
        """Update file processing status"""
        with self.get_session() as session:
            file_record = session.query(OCRFile).join(OCRJob).filter(
                OCRJob.job_id == job_id,
                OCRFile.file_path == file_path
            ).first()

            if not file_record:
                return False

            file_record.status = status
            if processing_time:
                file_record.processing_time = processing_time

            for key, value in updates.items():
                if hasattr(file_record, key):
                    setattr(file_record, key, value)

            # Update job counters
            job_record = file_record.job
            if status == "completed":
                job_record.processed_files += 1
            elif status == "failed":
                job_record.failed_files += 1

        return True

    def _create_audit_log(self, session: Session, job_id: int, event_type: str,
                         message: str, details: Dict[str, Any] = None):
        """Create audit log entry"""
        audit_log = AuditLog(
            job_id=job_id,
            event_type=event_type,
            message=message,
            details=details or {}
        )

        session.add(audit_log)

    def log_audit_event(self, job_id: str, event_type: str, message: str,
                       severity: str = "info", **details):
        """Log audit event for job"""
        with self.get_session() as session:
            job_record = session.query(OCRJob).filter_by(job_id=job_id).first()
            if job_record:
                self._create_audit_log(
                    session, job_record.id, event_type, message, details
                )

    def record_performance_metric(self, metric_name: str, metric_value: float,
                                metric_unit: str = None, job_id: str = None,
                                file_path: str = None, **context):
        """Record performance metric"""
        with self.get_session() as session:
            metric_record = PerformanceMetrics(
                metric_name=metric_name,
                metric_value=metric_value,
                metric_unit=metric_unit,
                context=context
            )

            # Link to job if provided
            if job_id:
                job_record = session.query(OCRJob).filter_by(job_id=job_id).first()
                if job_record:
                    metric_record.job_id = job_record.id

            # Link to file if provided
            if file_path:
                file_record = session.query(OCRFile).filter_by(file_path=file_path).first()
                if file_record:
                    metric_record.file_id = file_record.id

            session.add(metric_record)

    def get_job_history(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get job history with pagination"""
        with self.get_session() as session:
            jobs = session.query(OCRJob).order_by(
                OCRJob.created_at.desc()
            ).limit(limit).offset(offset).all()

            return [{
                'job_id': job.job_id,
                'status': job.status,
                'input_path': job.input_path,
                'mode': job.mode,
                'progress': job.progress,
                'created_at': job.created_at.isoformat(),
                'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                'processing_time': job.processing_time,
                'total_files': job.total_files,
                'processed_files': job.processed_files,
                'failed_files': job.failed_files
            } for job in jobs]

    def get_job_details(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed job information"""
        with self.get_session() as session:
            job_record = session.query(OCRJob).filter_by(job_id=job_id).first()
            if not job_record:
                return None

            # Get file details
            files = [{
                'file_name': file.file_name,
                'status': file.status,
                'processing_time': file.processing_time,
                'file_size': file.file_size,
                'error_message': file.error_message
            } for file in job_record.files]

            # Get recent audit logs
            audit_logs = [{
                'timestamp': log.timestamp.isoformat(),
                'event_type': log.event_type,
                'message': log.message,
                'severity': log.severity
            } for log in job_record.audit_logs[-10:]]  # Last 10 entries

            return {
                'job_id': job_record.job_id,
                'status': job_record.status,
                'input_path': job_record.input_path,
                'mode': job_record.mode,
                'language': job_record.language,
                'progress': job_record.progress,
                'created_at': job_record.created_at.isoformat(),
                'started_at': job_record.started_at.isoformat() if job_record.started_at else None,
                'completed_at': job_record.completed_at.isoformat() if job_record.completed_at else None,
                'processing_time': job_record.processing_time,
                'total_files': job_record.total_files,
                'processed_files': job_record.processed_files,
                'failed_files': job_record.failed_files,
                'output_path': job_record.output_path,
                'error_message': job_record.error_message,
                'files': files,
                'audit_logs': audit_logs,
                'metadata': job_record.metadata
            }

    def get_performance_report(self, days: int = 7) -> Dict[str, Any]:
        """Generate performance report"""
        with self.get_session() as session:
            # Calculate date range
            start_date = datetime.now() - timedelta(days=days)

            # Get completed jobs in date range
            jobs = session.query(OCRJob).filter(
                OCRJob.completed_at >= start_date,
                OCRJob.status == "completed"
            ).all()

            if not jobs:
                return {'message': 'No data available for the specified period'}

            # Calculate metrics
            total_jobs = len(jobs)
            total_files = sum(job.total_files for job in jobs)
            total_processing_time = sum(job.processing_time or 0 for job in jobs)

            successful_files = sum(job.processed_files for job in jobs)
            failed_files = sum(job.failed_files for job in jobs)

            avg_processing_time = total_processing_time / total_jobs if total_jobs > 0 else 0
            avg_files_per_job = total_files / total_jobs if total_jobs > 0 else 0

            return {
                'period_days': days,
                'total_jobs': total_jobs,
                'total_files': total_files,
                'successful_files': successful_files,
                'failed_files': failed_files,
                'success_rate': (successful_files / total_files * 100) if total_files > 0 else 0,
                'avg_processing_time': avg_processing_time,
                'avg_files_per_job': avg_files_per_job,
                'total_processing_time': total_processing_time
            }

    def cleanup_old_records(self, days_to_keep: int = 90):
        """Clean up old records for maintenance"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)

            with self.get_session() as session:
                # Delete old completed/failed jobs
                deleted_jobs = session.query(OCRJob).filter(
                    OCRJob.created_at < cutoff_date,
                    OCRJob.status.in_(["completed", "failed", "cancelled"])
                ).delete(synchronize_session=False)

                # Delete old audit logs
                deleted_audit = session.query(AuditLog).filter(
                    AuditLog.timestamp < cutoff_date
                ).delete(synchronize_session=False)

                # Delete old performance metrics
                deleted_metrics = session.query(PerformanceMetrics).filter(
                    PerformanceMetrics.timestamp < cutoff_date
                ).delete(synchronize_session=False)

            log_manager.logger.info(
                "Database cleanup completed",
                deleted_jobs=deleted_jobs,
                deleted_audit_logs=deleted_audit,
                deleted_metrics=deleted_metrics,
                cutoff_date=cutoff_date.isoformat()
            )

        except Exception as e:
            log_manager.logger.error("Database cleanup failed", error=str(e))


class DatabaseMigrationManager:
    """Handle database schema migrations"""

    def __init__(self, database_manager: DatabaseManager):
        self.db_manager = database_manager
        self.migration_dir = Path("migrations")

    def create_migration(self, message: str = "Auto migration"):
        """Create new migration script"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        migration_file = self.migration_dir / f"{timestamp}_{message.replace(' ', '_')}.py"

        migration_content = f'''"""
Database migration: {message}
Created: {datetime.now().isoformat()}
"""

from alembic import op
import sqlalchemy as sa
from database_manager import Base

def upgrade():
    # Add your upgrade logic here
    pass

def downgrade():
    # Add your downgrade logic here
    pass
'''

        self.migration_dir.mkdir(exist_ok=True)
        migration_file.write_text(migration_content)

        log_manager.logger.info(
            "Migration script created",
            migration_file=str(migration_file),
            message=message
        )

        return migration_file

    def run_migrations(self):
        """Run pending migrations"""
        try:
            # This would integrate with Alembic for production migrations
            # For now, just ensure tables exist
            Base.metadata.create_all(bind=self.db_manager.engine)

            log_manager.logger.info("Database migrations completed")

        except Exception as e:
            log_manager.logger.error("Migration execution failed", error=str(e))
            raise


# Global database manager instance
database_manager = None

def get_database_manager(config) -> Optional[DatabaseManager]:
    """Get or create global database manager"""
    global database_manager
    if database_manager is None and config.enable_database:
        database_manager = DatabaseManager(config)
    return database_manager