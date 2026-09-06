"""Server settings, separate from legacy local OCR defaults."""
from dataclasses import dataclass, fields
from pathlib import Path
import os


@dataclass(frozen=True)
class EnterpriseSettings:
    database_url: str = ''
    storage_root: Path = Path('data/enterprise')
    identity_url: str = ''
    identity_secret: str = ''
    global_concurrency: int = 2
    tenant_concurrency: int = 1
    lease_seconds: int = 60
    heartbeat_seconds: int = 10
    timeout_seconds: int = 1800
    retention_days: int = 30
    max_attempts: int = 3
    max_file_size: int = 100 * 1024 * 1024
    max_files_per_batch: int = 100
    max_pending_per_tenant: int = 1000
    maintenance_interval: int = 30
    audit_retention_days: int = 180
    upload_retention_hours: int = 24

    def __post_init__(self):
        if not self.database_url:
            raise ValueError('OCR_DATABASE_URL is required')
        for f in fields(self):
            if f.type is int and getattr(self, f.name) <= 0:
                raise ValueError(f'{f.name} must be positive')
        if self.heartbeat_seconds * 2 >= self.lease_seconds:
            raise ValueError('lease_seconds must exceed twice heartbeat_seconds')
        if self.identity_url and not self.identity_url.startswith(('https://', 'http://')):
            raise ValueError('Identity endpoint must use HTTP(S)')

    @classmethod
    def from_env(cls):
        values = {}
        for f in fields(cls):
            raw = os.getenv('OCR_' + f.name.upper())
            if raw is not None:
                values[f.name] = int(raw) if f.type is int else Path(raw) if f.type is Path else raw
        return cls(**values)
