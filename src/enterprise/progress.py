"""Durable job state, tenant authorization and fenced worker transitions."""
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
import hashlib
import json
import secrets
import shutil
from sqlalchemy import select, func, delete
from enterprise.database import Tenant, Upload, Batch, Job, Attempt, Event, APIKey, uid, utcnow
from enterprise.storage import LocalStorage, tenant_folder

ACTIVE = ('running', 'cancel_requested')
PENDING = ('queued', 'retry_wait')
TERMINAL = ('completed', 'failed', 'cancelled')


@dataclass(frozen=True)
class Claim:
    job_id: str
    attempt_id: str
    lease_token: str
    tenant_id: str
    source_key: str
    filename: str
    mode: str
    language: str


class DurableProgressTracker:
    def __init__(self, db, settings):
        self.db, self.settings = db, settings
        self.storage = LocalStorage(settings.storage_root)

    def _tenant(self, s, p):
        tenant = s.get(Tenant, p.tenant_id)
        if tenant is None:
            tenant = Tenant(id=p.tenant_id, retention_days=self.settings.retention_days, max_concurrent_jobs=self.settings.tenant_concurrency)
            s.add(tenant)
            s.flush()
        return tenant

    def _event(self, s, job, event, actor=None, detail=None):
        s.add(Event(tenant_id=job.tenant_id, job_id=job.id, actor_id=actor, event_type=event, detail=detail or {}))

    @staticmethod
    def _visible(p):
        filters = [Job.tenant_id == p.tenant_id, Job.deleted_at.is_(None)]
        if not p.manages_team:
            filters.append(Job.owner_id == p.user_id)
        return filters

    def _find(self, s, p, job_id, lock=False):
        query = select(Job).where(Job.id == job_id, *self._visible(p))
        return s.scalar(query.with_for_update() if lock else query)

    @staticmethod
    def _view(job):
        names = ('id', 'batch_id', 'tenant_id', 'owner_id', 'filename', 'mode', 'language', 'status', 'stage', 'attempt_count', 'error_code', 'error_message', 'created_at', 'started_at', 'completed_at', 'expires_at')
        result = {name: getattr(job, name) for name in names}
        result['artifacts'] = [{'kind': kind, 'filename': Path(key).name} for kind, key in (job.artifacts or {}).items()]
        return result

    def _batch_view(self, s, p, batch):
        jobs = s.scalars(select(Job).where(Job.batch_id == batch.id, *self._visible(p)).order_by(Job.created_at, Job.id)).all()
        statuses = {j.status for j in jobs}
        status = 'running' if statuses & set(ACTIVE) else 'queued' if statuses & set(PENDING) else 'completed' if statuses == {'completed'} else 'cancelled' if statuses == {'cancelled'} else 'failed' if statuses == {'failed'} else 'partial'
        return {'id': batch.id, 'status': status, 'jobs': [self._view(j) for j in jobs]}

    def register_upload(self, p, filename, storage_key, size):
        with self.db.session() as s:
            self.db.serialize(s)
            self._tenant(s, p)
            pending = s.scalar(select(func.count()).select_from(Upload).where(Upload.tenant_id == p.tenant_id, Upload.submitted_at.is_(None), Upload.deleted_at.is_(None)))
            if pending >= self.settings.max_pending_per_tenant:
                raise ValueError('upload_quota_exceeded')
            upload = Upload(tenant_id=p.tenant_id, owner_id=p.user_id, filename=filename, storage_key=storage_key, size=size)
            s.add(upload)
            s.flush()
            return {'id': upload.id, 'filename': filename, 'size': size}

    def create_batch(self, p, upload_ids, mode, language, idempotency_key):
        if not upload_ids or len(upload_ids) > self.settings.max_files_per_batch or len(set(upload_ids)) != len(upload_ids):
            raise ValueError('invalid_uploads')
        fingerprint = hashlib.sha256(json.dumps([upload_ids, mode, language], separators=(',', ':')).encode()).hexdigest()
        with self.db.session() as s:
            self.db.serialize(s)
            self._tenant(s, p)
            existing = s.scalar(select(Batch).where(Batch.tenant_id == p.tenant_id, Batch.owner_id == p.user_id, Batch.idempotency_key == idempotency_key))
            if existing:
                if existing.request_hash != fingerprint:
                    raise ValueError('idempotency_conflict')
                return self._batch_view(s, p, existing)
            pending = s.scalar(select(func.count()).select_from(Job).where(Job.tenant_id == p.tenant_id, Job.status.in_(PENDING + ACTIVE)))
            if pending + len(upload_ids) > self.settings.max_pending_per_tenant:
                raise ValueError('queue_quota_exceeded')
            uploads = s.scalars(select(Upload).where(Upload.id.in_(upload_ids), Upload.tenant_id == p.tenant_id, Upload.owner_id == p.user_id, Upload.submitted_at.is_(None), Upload.deleted_at.is_(None), Upload.created_at > utcnow() - timedelta(hours=self.settings.upload_retention_hours)).with_for_update()).all()
            if len(uploads) != len(upload_ids):
                raise ValueError('uploads_unavailable')
            batch = Batch(tenant_id=p.tenant_id, owner_id=p.user_id, idempotency_key=idempotency_key, request_hash=fingerprint)
            s.add(batch)
            s.flush()
            for upload in uploads:
                upload.submitted_at = utcnow()
                job = Job(tenant_id=p.tenant_id, owner_id=p.user_id, batch_id=batch.id, upload_id=upload.id, filename=upload.filename, mode=mode, language=language)
                s.add(job)
                s.flush()
                self._event(s, job, 'queued', p.user_id)
            return self._batch_view(s, p, batch)

    def get_job(self, p, job_id):
        with self.db.session() as s:
            job = self._find(s, p, job_id)
            return self._view(job) if job else None

    def list_jobs(self, p, q='', status=None, page=1, page_size=25, created_after=None, created_before=None, owner_id=None):
        with self.db.session() as s:
            filters = self._visible(p)
            if q:
                filters.append(Job.filename.ilike('%' + q.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%', escape='\\'))
            if status:
                filters.append(Job.status == status)
            if created_after:
                filters.append(Job.created_at >= created_after)
            if created_before:
                filters.append(Job.created_at <= created_before)
            if owner_id:
                filters.append(Job.owner_id == owner_id)
            total = s.scalar(select(func.count()).select_from(Job).where(*filters))
            jobs = s.scalars(select(Job).where(*filters).order_by(Job.created_at.desc(), Job.id).offset((page - 1) * page_size).limit(page_size)).all()
            return {'items': [self._view(j) for j in jobs], 'total': total, 'page': page, 'page_size': page_size}

    def get_batch(self, p, batch_id):
        with self.db.session() as s:
            filters = [Batch.id == batch_id, Batch.tenant_id == p.tenant_id]
            if not p.manages_team:
                filters.append(Batch.owner_id == p.user_id)
            batch = s.scalar(select(Batch).where(*filters))
            return self._batch_view(s, p, batch) if batch else None

    def events(self, p, job_id):
        with self.db.session() as s:
            if not self._find(s, p, job_id):
                return None
            events = s.scalars(select(Event).where(Event.job_id == job_id, Event.tenant_id == p.tenant_id).order_by(Event.created_at).limit(1000)).all()
            return {'items': [{'id': e.id, 'event_type': e.event_type, 'created_at': e.created_at, 'detail': e.detail} for e in events]}

    def claim(self, worker_id):
        now = utcnow()
        with self.db.session() as s:
            self.db.serialize(s)
            active = dict(s.execute(select(Job.tenant_id, func.count()).where(Job.status.in_(ACTIVE)).group_by(Job.tenant_id)).all())
            if sum(active.values()) >= self.settings.global_concurrency:
                return None
            limits = dict(s.execute(select(Tenant.id, Tenant.max_concurrent_jobs)).all())
            excluded = [t for t, count in active.items() if count >= limits.get(t, self.settings.tenant_concurrency)]
            query = select(Job).where(Job.status.in_(PENDING), Job.available_at <= now, Job.deleted_at.is_(None))
            if excluded:
                query = query.where(Job.tenant_id.not_in(excluded))
            job = s.scalar(query.order_by(Job.available_at, Job.created_at, Job.id).with_for_update(skip_locked=True).limit(1))
            if job is None:
                return None
            token = uid()
            job.status, job.stage = 'running', 'ocr'
            job.lease_token, job.lease_until, job.heartbeat_at = token, now + timedelta(seconds=self.settings.lease_seconds), now
            job.started_at = job.started_at or now
            job.attempt_count += 1
            job.cycle_attempts += 1
            attempt = Attempt(job_id=job.id, tenant_id=job.tenant_id, lease_token=token, worker_id=worker_id)
            s.add(attempt)
            s.flush()
            self._event(s, job, 'started', detail={'attempt': job.attempt_count})
            upload = s.get(Upload, job.upload_id)
            return Claim(job.id, attempt.id, token, job.tenant_id, upload.storage_key, job.filename, job.mode, job.language)

    def _leased(self, s, job_id, token, allow_cancel=False):
        return s.scalar(select(Job).where(Job.id == job_id, Job.lease_token == token, Job.lease_until > utcnow(), Job.status.in_(ACTIVE if allow_cancel else ('running',))).with_for_update())

    def heartbeat(self, job_id, token):
        with self.db.session() as s:
            job = self._leased(s, job_id, token)
            if not job:
                return False
            job.heartbeat_at = utcnow()
            job.lease_until = utcnow() + timedelta(seconds=self.settings.lease_seconds)
            return True

    def cancelled(self, job_id, token):
        with self.db.session() as s:
            return s.scalar(select(Job.id).where(Job.id == job_id, Job.lease_token == token, Job.status == 'cancel_requested')) is not None

    def _end_attempt(self, s, job, status):
        attempt = s.scalar(select(Attempt).where(Attempt.lease_token == job.lease_token))
        if attempt:
            attempt.status, attempt.completed_at = status, utcnow()
        job.lease_until = None
        job.lease_token = None

    def _terminal(self, s, job, status):
        self._end_attempt(s, job, status)
        job.status, job.stage, job.completed_at = status, status, utcnow()
        tenant = s.get(Tenant, job.tenant_id)
        job.expires_at = job.completed_at + timedelta(days=tenant.retention_days)
        self._event(s, job, status)

    def complete(self, job_id, token, artifacts):
        with self.db.session() as s:
            job = self._leased(s, job_id, token)
            if not job:
                return False
            attempt = s.scalar(select(Attempt).where(Attempt.lease_token == token))
            prefix = f'{tenant_folder(job.tenant_id)}/jobs/{job.id}/{attempt.id}/'
            if not {'pdf', 'text', 'log'} <= artifacts.keys() or any(not key.startswith(prefix) or not self.storage.path(key).is_file() for key in artifacts.values()):
                raise ValueError('invalid_artifacts')
            for key in artifacts.values():
                with self.storage.path(key).open('rb') as file:
                    import os
                    os.fsync(file.fileno())
                self.storage.sync_parent(self.storage.path(key))
            job.artifacts = artifacts
            job.error_code = job.error_message = None
            self._terminal(s, job, 'completed')
            return True

    def _failure(self, s, job, code, message, retryable):
        job.error_code, job.error_message = code, message
        if retryable and job.cycle_attempts < self.settings.max_attempts:
            self._end_attempt(s, job, 'failed')
            job.status, job.stage = 'retry_wait', 'retry_wait'
            job.available_at = utcnow() + timedelta(seconds=10 * (2 ** (job.cycle_attempts - 1)))
            self._event(s, job, 'retry_scheduled', detail={'error_code': code})
        else:
            self._terminal(s, job, 'failed')

    def fail(self, job_id, token, error_code, message, retryable=True):
        with self.db.session() as s:
            job = self._leased(s, job_id, token)
            if not job:
                return False
            self._failure(s, job, error_code, message, retryable)
            return True

    def finish_cancel(self, job_id, token):
        with self.db.session() as s:
            job = self._leased(s, job_id, token, allow_cancel=True)
            if not job or job.status != 'cancel_requested':
                return False
            self._terminal(s, job, 'cancelled')
            return True

    def recover(self):
        with self.db.session() as s:
            self.db.serialize(s)
            jobs = s.scalars(select(Job).where(Job.status.in_(ACTIVE), Job.lease_until <= utcnow()).with_for_update(skip_locked=True)).all()
            for job in jobs:
                if job.status == 'cancel_requested':
                    self._terminal(s, job, 'cancelled')
                else:
                    self._failure(s, job, 'worker_lost', 'העיבוד הופסק; מתבצע ניסיון התאוששות.', True)
            return len(jobs)

    def cancel(self, p, job_id):
        with self.db.session() as s:
            job = self._find(s, p, job_id, lock=True)
            if not job:
                return None
            if job.status in PENDING:
                self._terminal(s, job, 'cancelled')
            elif job.status == 'running':
                job.status, job.stage = 'cancel_requested', 'cancel_requested'
                self._event(s, job, 'cancel_requested', p.user_id)
            return self._view(job)

    def retry(self, p, job_id):
        with self.db.session() as s:
            job = self._find(s, p, job_id, lock=True)
            if not job:
                return None
            if job.status not in ('failed', 'cancelled'):
                raise ValueError('job_not_retryable')
            if job.expires_at and job.expires_at <= utcnow():
                raise ValueError('job_expired')
            job.status = job.stage = 'queued'
            job.cycle_attempts = 0
            job.available_at = utcnow()
            job.completed_at = job.expires_at = None
            job.error_code = job.error_message = None
            self._event(s, job, 'manual_retry', p.user_id)
            return self._view(job)

    def artifact(self, p, job_id, kind):
        with self.db.session() as s:
            job = self._find(s, p, job_id)
            if not job or job.status != 'completed' or (job.expires_at and job.expires_at <= utcnow()):
                return None
            key = (job.artifacts or {}).get(kind)
            return self.storage.path(key) if key else None

    def delete_job(self, p, job_id):
        with self.db.session() as s:
            job = self._find(s, p, job_id, lock=True)
            if not job:
                return False
            if job.status not in TERMINAL:
                raise ValueError('cancel_before_delete')
            job.deleted_at = utcnow()
            self._event(s, job, 'deleted', p.user_id)
        self.cleanup()
        return True

    def cleanup(self):
        removed_jobs = removed_uploads = 0
        now = utcnow()
        with self.db.session() as s:
            self.db.serialize(s)
            jobs = s.scalars(select(Job).where(Job.status.in_(TERMINAL), (Job.expires_at <= now) | Job.deleted_at.is_not(None)).with_for_update(skip_locked=True)).all()
            for job in jobs:
                upload = s.get(Upload, job.upload_id)
                if upload and upload.storage_key:
                    self.storage.path(upload.storage_key).unlink(missing_ok=True)
                    upload.storage_key, upload.filename, upload.deleted_at = '', '', now
                    removed_uploads += 1
                root = self.storage.path(f'{tenant_folder(job.tenant_id)}/jobs/{job.id}')
                if root.exists():
                    shutil.rmtree(root)
                job.deleted_at = job.deleted_at or now
                job.artifacts, job.filename, job.error_message = {}, '', None
                removed_jobs += 1
            uploads = s.scalars(select(Upload).where(Upload.submitted_at.is_(None), Upload.deleted_at.is_(None), Upload.created_at <= now - timedelta(hours=self.settings.upload_retention_hours)).with_for_update(skip_locked=True)).all()
            for upload in uploads:
                self.storage.path(upload.storage_key).unlink(missing_ok=True)
                upload.storage_key, upload.filename, upload.deleted_at = '', '', now
                removed_uploads += 1
            s.execute(delete(Event).where(Event.created_at < now - timedelta(days=self.settings.audit_retention_days)))
        return {'jobs': removed_jobs, 'uploads': removed_uploads}

    def settings_view(self, p):
        with self.db.session() as s:
            self.db.serialize(s)
            tenant = self._tenant(s, p)
            return {'retention_days': tenant.retention_days, 'max_concurrent_jobs': tenant.max_concurrent_jobs}

    def update_settings(self, p, values):
        with self.db.session() as s:
            self.db.serialize(s)
            tenant = self._tenant(s, p)
            for key, value in values.items():
                setattr(tenant, key, value)
            s.add(Event(tenant_id=p.tenant_id, actor_id=p.user_id, event_type='settings_updated', detail=values))
            return {'retention_days': tenant.retention_days, 'max_concurrent_jobs': tenant.max_concurrent_jobs}

    def list_keys(self, p):
        with self.db.session() as s:
            keys = s.scalars(select(APIKey).where(APIKey.tenant_id == p.tenant_id).order_by(APIKey.created_at.desc())).all()
            return {'items': [{k: getattr(key, k) for k in ('id', 'name', 'scopes', 'created_at', 'revoked_at')} for key in keys]}

    def create_key(self, p, name, scopes):
        token = 'ocr_' + secrets.token_urlsafe(32)
        with self.db.session() as s:
            self.db.serialize(s)
            self._tenant(s, p)
            key = APIKey(tenant_id=p.tenant_id, owner_id=p.user_id, name=name, scopes=scopes, token_hash=hashlib.sha256(token.encode()).hexdigest())
            s.add(key)
            s.flush()
            s.add(Event(tenant_id=p.tenant_id, actor_id=p.user_id, event_type='key_created', detail={'key_id': key.id}))
            return {'id': key.id, 'name': name, 'scopes': scopes, 'token': token, 'created_at': key.created_at, 'revoked_at': None}

    def revoke_key(self, p, key_id):
        with self.db.session() as s:
            key = s.scalar(select(APIKey).where(APIKey.id == key_id, APIKey.tenant_id == p.tenant_id).with_for_update())
            if not key:
                return False
            key.revoked_at = utcnow()
            s.add(Event(tenant_id=p.tenant_id, actor_id=p.user_id, event_type='key_revoked', detail={'key_id': key.id}))
            return True
