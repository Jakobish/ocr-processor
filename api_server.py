"""
Enterprise OCR REST API Server
Provides HTTP API endpoints for job management, monitoring, and integration
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from typing import Dict, Any, Optional, List
from pathlib import Path
import uvicorn
import threading
from datetime import datetime
from logger import log_manager
from config import config
from progress_tracker import progress_tracker
from security_validator import security_validator
from notification_manager import get_notification_manager
from database_manager import get_database_manager


# Pydantic models for API
class OCRJobCreate(BaseModel):
    """Request model for creating OCR job"""
    input_path: str = Field(..., description="Path to PDF file or directory")
    mode: str = Field(default="cli", description="OCR processing mode")
    language: str = Field(default="heb+eng", description="Language for OCR")
    priority: str = Field(default="normal", description="Job priority")
    recursive: bool = Field(default=True, description="Process directories recursively")
    archive_originals: bool = Field(default=False, description="Archive original files")
    webhook_url: Optional[str] = Field(None, description="Webhook URL for notifications")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @validator('mode')
    def validate_mode(cls, v):
        if v not in ['cli', 'force', 'visual']:
            raise ValueError('Mode must be one of: cli, force, visual')
        return v

    @validator('priority')
    def validate_priority(cls, v):
        if v not in ['low', 'normal', 'high', 'urgent']:
            raise ValueError('Priority must be one of: low, normal, high, urgent')
        return v


class OCRJobResponse(BaseModel):
    """Response model for OCR job information"""
    job_id: str
    status: str
    progress: float
    input_path: str
    mode: str
    language: str
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    total_files: int
    processed_files: int
    failed_files: int
    output_path: Optional[str]
    error_message: Optional[str]
    metadata: Dict[str, Any]


class BatchJobCreate(BaseModel):
    """Request model for batch job creation"""
    files: List[str] = Field(..., description="List of file paths to process")
    mode: str = Field(default="cli", description="OCR processing mode")
    language: str = Field(default="heb+eng", description="Language for OCR")
    priority: str = Field(default="normal", description="Job priority")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class SystemStatus(BaseModel):
    """System status response"""
    status: str
    version: str
    uptime_seconds: float
    active_jobs: int
    total_jobs: int
    system_metrics: Dict[str, Any]
    database_enabled: bool
    notifications_enabled: bool


class MetricsResponse(BaseModel):
    """Metrics response model"""
    performance: Dict[str, Any]
    system: Dict[str, Any]
    jobs: Dict[str, Any]
    timestamp: datetime


class HealthCheck(BaseModel):
    """Health check response"""
    status: str
    timestamp: datetime
    services: Dict[str, str]
    database: str
    storage: str


# API Dependencies
async def get_api_key(credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())):
    """Validate API key for authentication"""
    # In production, validate against secure storage
    expected_api_key = "your-secure-api-key-here"  # Should be from environment variable
    if credentials.credentials != expected_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    return credentials.credentials


class OCRAPIServer:
    """Main API server class"""

    def __init__(self, config):
        self.config = config
        self.app = FastAPI(
            title="OCR Processor Enterprise API",
            description="Enterprise-grade OCR processing API with job management and monitoring",
            version="2.0.0",
            docs_url="/docs" if config.enable_api else None,
            redoc_url="/redoc" if config.enable_api else None
        )

        # Initialize components
        self.notification_manager = get_notification_manager(config)
        self.database_manager = get_database_manager(config)

        # Setup middleware and routes
        self._setup_middleware()
        self._setup_routes()

        # Start time for uptime tracking
        self.start_time = datetime.now()

    def _setup_middleware(self):
        """Setup API middleware"""
        # CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=self.config.api_cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["*"],
        )

        # Custom middleware for request logging
        @self.app.middleware("http")
        async def log_requests(request, call_next):
            start_time = datetime.now()

            # Log request
            log_manager.logger.info(
                "API request",
                method=request.method,
                url=str(request.url),
                client=request.client.host if request.client else "unknown",
                event_type="api_request"
            )

            response = await call_next(request)

            # Log response
            process_time = (datetime.now() - start_time).total_seconds()
            log_manager.logger.info(
                "API response",
                method=request.method,
                url=str(request.url),
                status_code=response.status_code,
                process_time=process_time,
                event_type="api_response"
            )

            return response

    def _setup_routes(self):
        """Setup API routes"""

        @self.app.get("/health", response_model=HealthCheck)
        async def health_check():
            """Health check endpoint"""
            services_status = {}

            # Check database
            db_status = "healthy"
            if self.database_manager:
                try:
                    with self.database_manager.get_session() as session:
                        session.execute("SELECT 1")
                    services_status["database"] = "connected"
                except Exception as e:
                    db_status = "unhealthy"
                    services_status["database"] = f"error: {str(e)[:100]}"

            # Check storage
            storage_status = "healthy"
            try:
                # Check if we can write to output directory
                test_file = Path("test_write_permission")
                test_file.write_text("test")
                test_file.unlink()
                services_status["storage"] = "writable"
            except Exception as e:
                storage_status = "unhealthy"
                services_status["storage"] = f"error: {str(e)[:100]}"

            overall_status = "healthy" if db_status == "healthy" and storage_status == "healthy" else "unhealthy"

            return HealthCheck(
                status=overall_status,
                timestamp=datetime.now(),
                services=services_status,
                database=db_status,
                storage=storage_status
            )

        @self.app.get("/status", response_model=SystemStatus)
        async def system_status():
            """Get system status"""
            queue_status = progress_tracker.get_queue_status()

            return SystemStatus(
                status="running",
                version="2.0.0",
                uptime_seconds=(datetime.now() - self.start_time).total_seconds(),
                active_jobs=queue_status.get('active_jobs', 0),
                total_jobs=queue_status.get('total_jobs', 0),
                system_metrics={},  # Would be populated from metrics collector
                database_enabled=config.enable_database,
                notifications_enabled=config.enable_notifications
            )

        @self.app.post("/jobs", response_model=Dict[str, str])
        async def create_job(job_request: OCRJobCreate, background_tasks: BackgroundTasks):
            """Create new OCR processing job"""
            try:
                # Validate input path
                validation_result = security_validator.validate_input_path(job_request.input_path)
                if not validation_result.is_valid:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Input validation failed: {', '.join(validation_result.issues)}"
                    )

                # Create job
                job_id = progress_tracker.create_job(
                    input_path=job_request.input_path,
                    mode=job_request.mode,
                    language=job_request.language,
                    priority=job_request.priority,
                    recursive=job_request.recursive,
                    archive_originals=job_request.archive_originals,
                    webhook_url=job_request.webhook_url,
                    metadata=job_request.metadata
                )

                # Add to database if enabled
                if self.database_manager:
                    self.database_manager.create_job_record(
                        job_id=job_id,
                        input_path=job_request.input_path,
                        mode=job_request.mode,
                        language=job_request.language,
                        **job_request.metadata
                    )

                # Start job in background
                background_tasks.add_task(self._process_job_background, job_id)

                log_manager.logger.info(
                    "Job created via API",
                    job_id=job_id,
                    input_path=job_request.input_path,
                    mode=job_request.mode
                )

                return {"job_id": job_id, "status": "created"}

            except Exception as e:
                log_manager.logger.error("API job creation failed", error=str(e))
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/jobs/{job_id}", response_model=OCRJobResponse)
        async def get_job_status(job_id: str):
            """Get job status"""
            job_status = progress_tracker.get_job_status(job_id)
            if not job_status:
                raise HTTPException(status_code=404, detail="Job not found")

            return OCRJobResponse(**job_status)

        @self.app.delete("/jobs/{job_id}")
        async def cancel_job(job_id: str):
            """Cancel job"""
            progress_tracker.cancel_job(job_id)

            # Update database if enabled
            if self.database_manager:
                self.database_manager.update_job_status(job_id, "cancelled")

            return {"message": "Job cancelled"}

        @self.app.get("/jobs", response_model=Dict[str, Any])
        async def list_jobs(limit: int = 50, offset: int = 0):
            """List all jobs with pagination"""
            jobs = progress_tracker.get_all_jobs()

            # Apply pagination
            job_items = list(jobs.values())
            paginated_jobs = job_items[offset:offset + limit]

            return {
                "jobs": paginated_jobs,
                "total": len(job_items),
                "limit": limit,
                "offset": offset
            }

        @self.app.get("/metrics", response_model=MetricsResponse)
        async def get_metrics():
            """Get system metrics"""
            # This would integrate with the metrics collector
            return MetricsResponse(
                performance={},
                system={},
                jobs=progress_tracker.get_queue_status(),
                timestamp=datetime.now()
            )

        @self.app.post("/batch")
        async def create_batch_job(batch_request: BatchJobCreate, background_tasks: BackgroundTasks):
            """Create batch processing job"""
            try:
                # Validate all input files
                valid_files = []
                for file_path in batch_request.files:
                    validation_result = security_validator.validate_input_path(file_path)
                    if validation_result.is_valid:
                        valid_files.append(file_path)
                    else:
                        log_manager.logger.warning(
                            "Invalid file in batch",
                            file_path=file_path,
                            issues=validation_result.issues
                        )

                if not valid_files:
                    raise HTTPException(status_code=400, detail="No valid files provided")

                # Create batch job
                batch_job_id = f"batch_{int(datetime.now().timestamp())}"

                # Create individual jobs for each file
                job_ids = []
                for file_path in valid_files:
                    job_id = progress_tracker.create_job(
                        input_path=file_path,
                        mode=batch_request.mode,
                        language=batch_request.language,
                        priority=batch_request.priority,
                        metadata={
                            **batch_request.metadata,
                            "batch_job_id": batch_job_id
                        }
                    )
                    job_ids.append(job_id)

                    # Add to database if enabled
                    if self.database_manager:
                        self.database_manager.create_job_record(
                            job_id=job_id,
                            input_path=file_path,
                            mode=batch_request.mode,
                            language=batch_request.language,
                            **batch_request.metadata
                        )

                    # Start each job
                    background_tasks.add_task(self._process_job_background, job_id)

                return {
                    "batch_job_id": batch_job_id,
                    "job_ids": job_ids,
                    "total_files": len(valid_files),
                    "status": "created"
                }

            except Exception as e:
                log_manager.error("Batch job creation failed", error=str(e))
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/upload")
        async def upload_file(
            background_tasks: BackgroundTasks,
            file: UploadFile = File(...),
            mode: str = Form("cli"),
            language: str = Form("heb+eng"),
            priority: str = Form("normal")
        ):
            """Upload file for OCR processing"""
            try:
                # Validate file
                if not file.filename.lower().endswith('.pdf'):
                    raise HTTPException(status_code=400, detail="Only PDF files are supported")

                # Create temporary file
                temp_dir = Path("temp_uploads")
                temp_dir.mkdir(exist_ok=True)

                temp_file_path = temp_dir / f"{int(datetime.now().timestamp())}_{file.filename}"

                # Save uploaded file
                with open(temp_file_path, "wb") as buffer:
                    content = await file.read()
                    buffer.write(content)

                # Validate saved file
                validation_result = security_validator.validate_pdf_file(temp_file_path)
                if not validation_result.is_valid:
                    temp_file_path.unlink()  # Clean up
                    raise HTTPException(
                        status_code=400,
                        detail=f"File validation failed: {', '.join(validation_result.issues)}"
                    )

                # Create job
                job_id = progress_tracker.create_job(
                    input_path=str(temp_file_path),
                    mode=mode,
                    language=language,
                    priority=priority,
                    metadata={"uploaded_file": True, "original_filename": file.filename}
                )

                # Add to database if enabled
                if self.database_manager:
                    self.database_manager.create_job_record(
                        job_id=job_id,
                        input_path=str(temp_file_path),
                        mode=mode,
                        language=language
                    )

                # Start processing in background
                background_tasks.add_task(self._process_job_background, job_id)

                return {"job_id": job_id, "status": "created", "file_path": str(temp_file_path)}

            except HTTPException:
                raise
            except Exception as e:
                log_manager.logger.error("File upload failed", error=str(e))
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/download/{job_id}")
        async def download_results(job_id: str):
            """Download job results"""
            job_status = progress_tracker.get_job_status(job_id)
            if not job_status:
                raise HTTPException(status_code=404, detail="Job not found")

            if job_status['status'] != 'completed':
                raise HTTPException(status_code=400, detail="Job not completed")

            # This would return the processed files
            # Implementation depends on how results are stored
            return {"message": "Download endpoint - implementation needed"}

    async def _process_job_background(self, job_id: str):
        """Process job in background"""
        try:
            # This would integrate with the existing OCR processing logic
            # For now, simulate processing
            import time

            progress_tracker.start_job(job_id)

            # Simulate progress updates
            for i in range(10):
                progress_tracker.update_progress(
                    job_id=job_id,
                    progress=(i + 1) * 10,
                    current_file=f"Processing file {i + 1}",
                    processed_files=i + 1
                )
                time.sleep(1)

            # Complete job
            progress_tracker.complete_job(job_id, success=True)

            # Send notification
            job_status = progress_tracker.get_job_status(job_id)
            if job_status:
                self.notification_manager.send_job_completion_notification(
                    job_id=job_id,
                    success=True,
                    job_details=job_status
                )

        except Exception as e:
            log_manager.logger.error(
                "Background job processing failed",
                job_id=job_id,
                error=str(e)
            )

            progress_tracker.complete_job(job_id, success=False, error_message=str(e))

            # Send failure notification
            job_status = progress_tracker.get_job_status(job_id)
            if job_status:
                self.notification_manager.send_job_completion_notification(
                    job_id=job_id,
                    success=False,
                    job_details={**job_status, 'error_message': str(e)}
                )

    def start_server(self):
        """Start the API server"""
        if not self.config.enable_api:
            log_manager.logger.info("API server disabled in configuration")
            return

        log_manager.logger.info(
            "Starting API server",
            host=self.config.api_host,
            port=self.config.api_port
        )

        uvicorn.run(
            self.app,
            host=self.config.api_host,
            port=self.config.api_port,
            log_level=self.config.log_level.lower()
        )


# Global API server instance
api_server = None

def get_api_server(config) -> OCRAPIServer:
    """Get or create global API server"""
    global api_server
    if api_server is None:
        api_server = OCRAPIServer(config)
    return api_server


def start_api_server():
    """Start API server in separate thread"""
    if config.enable_api:
        api_thread = threading.Thread(target=lambda: get_api_server(config).start_server(), daemon=True)
        api_thread.start()
        return api_thread
    return None