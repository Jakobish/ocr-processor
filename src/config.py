"""
Enterprise OCR Configuration Management
Provides centralized configuration with environment variable support and validation
"""
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

@dataclass
class OCRConfig:
    """Enterprise OCR Processing Configuration"""

    # Processing Settings
    default_language: str = "heb+eng"
    processing_modes: list = field(default_factory=lambda: ["cli", "force", "visual"])
    default_mode: str = "cli"

    # Performance Settings
    max_concurrent_jobs: int = 4
    chunk_size: int = 10
    timeout_per_file: int = 300  # seconds
    max_file_size: int = 100 * 1024 * 1024  # 100MB

    # Output Settings
    output_base_dir: str = "ocr_output"
    archive_originals: bool = True
    create_zip_archives: bool = True
    preserve_structure: bool = True

    # Logging Settings
    log_level: str = "INFO"
    log_to_file: bool = True
    log_directory: str = "logs"
    log_rotation_size: str = "10 MB"
    enable_remote_logging: bool = False
    remote_log_url: str = ""

    # Notification Settings
    enable_notifications: bool = False
    smtp_server: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    notification_email: str = ""
    webhook_url: str = ""

    # Database Settings
    enable_database: bool = False
    database_url: str = ""
    database_table_prefix: str = "ocr_"

    # Security Settings
    allowed_extensions: list = field(default_factory=lambda: [".pdf"])
    max_files_per_job: int = 1000
    enable_file_validation: bool = True
    quarantine_suspicious: bool = True

    # API Settings
    enable_api: bool = False
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_cors_origins: list = field(default_factory=lambda: ["*"])

    # Docker Settings
    enable_docker: bool = False
    docker_image: str = "ocr-processor:latest"
    docker_network: str = "ocr-network"

    def __post_init__(self):
        """Load configuration from environment variables and config file"""
        self._load_from_env()
        self._load_from_file()
        self._validate_config()

    def _load_from_env(self):
        """Load configuration from environment variables"""
        # Processing settings
        if os.getenv("OCR_DEFAULT_LANGUAGE"):
            self.default_language = os.getenv("OCR_DEFAULT_LANGUAGE")
        if os.getenv("OCR_DEFAULT_MODE"):
            self.default_mode = os.getenv("OCR_DEFAULT_MODE")

        # Performance settings
        if os.getenv("OCR_MAX_CONCURRENT_JOBS"):
            self.max_concurrent_jobs = int(os.getenv("OCR_MAX_CONCURRENT_JOBS"))
        if os.getenv("OCR_TIMEOUT_PER_FILE"):
            self.timeout_per_file = int(os.getenv("OCR_TIMEOUT_PER_FILE"))
        if os.getenv("OCR_MAX_FILE_SIZE"):
            self.max_file_size = int(os.getenv("OCR_MAX_FILE_SIZE"))

        # Output settings
        if os.getenv("OCR_OUTPUT_BASE_DIR"):
            self.output_base_dir = os.getenv("OCR_OUTPUT_BASE_DIR")
        if os.getenv("OCR_ARCHIVE_ORIGINALS"):
            self.archive_originals = os.getenv("OCR_ARCHIVE_ORIGINALS").lower() == "true"
        if os.getenv("OCR_CREATE_ZIP"):
            self.create_zip_archives = os.getenv("OCR_CREATE_ZIP").lower() == "true"

        # Logging settings
        if os.getenv("OCR_LOG_LEVEL"):
            self.log_level = os.getenv("OCR_LOG_LEVEL")
        if os.getenv("OCR_LOG_TO_FILE"):
            self.log_to_file = os.getenv("OCR_LOG_TO_FILE").lower() == "true"
        if os.getenv("OCR_LOG_DIRECTORY"):
            self.log_directory = os.getenv("OCR_LOG_DIRECTORY")
        if os.getenv("OCR_REMOTE_LOG_URL"):
            self.remote_log_url = os.getenv("OCR_REMOTE_LOG_URL")
            self.enable_remote_logging = True

        # Notification settings
        if os.getenv("OCR_SMTP_SERVER"):
            self.smtp_server = os.getenv("OCR_SMTP_SERVER")
        if os.getenv("OCR_SMTP_PORT"):
            self.smtp_port = int(os.getenv("OCR_SMTP_PORT"))
        if os.getenv("OCR_NOTIFICATION_EMAIL"):
            self.notification_email = os.getenv("OCR_NOTIFICATION_EMAIL")
            self.enable_notifications = True
        if os.getenv("OCR_WEBHOOK_URL"):
            self.webhook_url = os.getenv("OCR_WEBHOOK_URL")
            self.enable_notifications = True

        # Database settings
        if os.getenv("OCR_DATABASE_URL"):
            self.database_url = os.getenv("OCR_DATABASE_URL")
            self.enable_database = True

        # API settings
        if os.getenv("OCR_API_PORT"):
            self.api_port = int(os.getenv("OCR_API_PORT"))
        if os.getenv("OCR_API_HOST"):
            self.api_host = os.getenv("OCR_API_HOST")

    def _load_from_file(self):
        """Load configuration from config file if it exists"""
        config_paths = [
            Path.cwd() / "ocr_config.json",
            Path.home() / ".ocr_config.json",
            Path("/etc/ocr-processor/config.json")
        ]

        for config_path in config_paths:
            if config_path.exists():
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        self._update_from_dict(data)
                        print(f"📋 Loaded configuration from: {config_path}")
                        break
                except Exception as e:
                    print(f"⚠️ Failed to load config from {config_path}: {e}")

    def _update_from_dict(self, data: Dict[str, Any]):
        """Update configuration from dictionary"""
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def _validate_config(self):
        """Validate configuration settings"""
        # Validate processing modes
        valid_modes = ["cli", "force", "visual"]
        if self.default_mode not in valid_modes:
            raise ValueError(f"Invalid default mode: {self.default_mode}")

        # Validate language format
        valid_langs = ["heb+eng", "eng", "heb", "eng+fra", "eng+deu", "eng+spa"]
        if self.default_language not in valid_langs:
            print(f"⚠️ Warning: Uncommon language setting: {self.default_language}")

        # Validate file size
        if self.max_file_size <= 0:
            raise ValueError("Max file size must be positive")

        # Validate concurrent jobs
        if self.max_concurrent_jobs <= 0:
            raise ValueError("Max concurrent jobs must be positive")

    def save_to_file(self, config_path: Optional[Path] = None) -> Path:
        """Save current configuration to file"""
        if not config_path:
            config_path = Path.cwd() / "ocr_config.json"

        config_dict = {}
        for key, value in self.__dict__.items():
            if not key.startswith('_'):
                config_dict[key] = value

        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=2, ensure_ascii=False)

        print(f"💾 Configuration saved to: {config_path}")
        return config_path

    def get_ocr_settings(self, mode: str, language: Optional[str] = None) -> Dict[str, Any]:
        """Get OCR settings based on current configuration"""
        base_settings = {
            'deskew': True,
            'output_type': 'pdfa',
            'progress_bar': not self.enable_api,  # Disable progress bar for API mode
            'skip_big': False,
            'fast_web_view': True,
            'optimize_images': True,
            'clean': True,
            'lang': language or self.default_language,
            'clean_final': True,
            'oversample': 300,
            'jobs': min(self.max_concurrent_jobs, os.cpu_count() or 1),
            'tesseract_config': '--psm 3',
        }

        if mode == "cli":
            base_settings.update({'force_ocr': False, 'skip_text': True})
        elif mode == "force":
            base_settings.update({'force_ocr': True, 'skip_text': False})
        elif mode == "visual":
            base_settings.update({'force_ocr': False, 'skip_text': True})
        else:
            raise ValueError(f"Unknown mode: {mode}")

        return base_settings

    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration"""
        return {
            'level': self.log_level,
            'log_to_file': self.log_to_file,
            'log_directory': self.log_directory,
            'enable_remote_logging': self.enable_remote_logging,
            'remote_log_url': self.remote_log_url,
        }


# Global configuration instance
config = OCRConfig()