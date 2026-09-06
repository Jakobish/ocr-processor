"""Private local storage with generated keys; never accepts client paths."""
import hashlib
import os
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
from ocr_utils import FileUtils


def tenant_folder(tenant_id):
    return hashlib.sha256(tenant_id.encode()).hexdigest()


class LocalStorage:
    def __init__(self, root):
        self.root = Path(root).resolve()
        FileUtils.ensure_dir(self.root)

    def path(self, key):
        keypath = Path(key)
        if keypath.is_absolute() or '..' in keypath.parts or not key:
            raise ValueError('Invalid storage key')
        path = (self.root / keypath).resolve()
        if not path.is_relative_to(self.root) or path == self.root:
            raise ValueError('Invalid storage key')
        return path

    def upload_key(self, tenant_id):
        return f'{tenant_folder(tenant_id)}/uploads/{uuid4()}.pdf'

    def attempt_dir(self, tenant_id, job_id, attempt_id, mode, filename):
        # Human filename deliberately not used as a path component.
        stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        key = f'{tenant_folder(tenant_id)}/jobs/{job_id}/{attempt_id}/ocr_{mode}/document_{stamp}'
        return key, FileUtils.ensure_dir(self.path(key))

    def sync(self, file):
        file.flush()
        os.fsync(file.fileno())

    def sync_parent(self, path):
        fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
