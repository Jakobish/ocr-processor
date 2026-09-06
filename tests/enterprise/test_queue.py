import os
import sys
from pathlib import Path
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from enterprise.database import Database, Base, Job, Attempt, utcnow
from enterprise.settings import EnterpriseSettings
from enterprise.progress import DurableProgressTracker
from enterprise.identity import Principal

@pytest.fixture
def env(tmp_path):
    url = os.getenv('OCR_TEST_DATABASE_URL', f'sqlite:///{tmp_path}/test.db')
    db = Database(url)
    Base.metadata.drop_all(db.engine)
    Base.metadata.create_all(db.engine)
    settings = EnterpriseSettings(database_url=url, storage_root=tmp_path / 'files')
    tracker = DurableProgressTracker(db, settings)
    yield db, tracker, settings
    db.engine.dispose()


def submit(tracker, tenant='alpha', user='alice', count=1, key='first'):
    p = Principal(user_id=user, tenant_id=tenant, role='member')
    ids = [tracker.register_upload(p, f'file{i}.pdf', f'{tenant}/uploads/{key}-{i}.pdf', 100)['id'] for i in range(count)]
    return tracker.create_batch(p, ids, 'cli', 'heb+eng', key)


def test_submission_is_durable_and_idempotent(env):
    db, tracker, settings = env
    p = Principal(user_id='alice', tenant_id='alpha', role='member')
    upload = tracker.register_upload(p, 'a.pdf', 'alpha/uploads/a.pdf', 100)
    first = tracker.create_batch(p, [upload['id']], 'cli', 'heb+eng', 'request-1')
    again = DurableProgressTracker(Database(settings.database_url), settings)
    assert again.create_batch(p, [upload['id']], 'cli', 'heb+eng', 'request-1')['id'] == first['id']
    assert again.list_jobs(p)['total'] == 1
    with pytest.raises(ValueError, match='idempotency'):
        again.create_batch(p, [upload['id']], 'force', 'heb+eng', 'request-1')


def test_tenant_and_owner_limits_fence_reads(env):
    _, tracker, _ = env
    result = submit(tracker)
    job_id = result['jobs'][0]['id']
    assert tracker.get_job(Principal('bob', 'beta', 'owner'), job_id) is None
    assert tracker.get_job(Principal('bob', 'alpha', 'member'), job_id) is None
    assert tracker.get_job(Principal('bob', 'alpha', 'admin'), job_id)['id'] == job_id


def test_claim_respects_global_and_team_limits(env):
    _, tracker, _ = env
    submit(tracker, count=2)
    submit(tracker, tenant='beta', key='second')
    a = tracker.claim('one')
    b = tracker.claim('two')
    assert a.tenant_id != b.tenant_id
    assert tracker.claim('three') is None


def test_expired_lease_recovers_and_old_worker_cannot_publish(env):
    db, tracker, _ = env
    submit(tracker)
    first = tracker.claim('worker-old')
    with db.session() as s:
        job = s.get(Job, first.job_id)
        job.lease_until = utcnow() - timedelta(seconds=1)
    assert tracker.recover() == 1
    with db.session() as s:
        s.get(Job, first.job_id).available_at = utcnow() - timedelta(seconds=1)
    second = tracker.claim('worker-new')
    assert second.lease_token != first.lease_token
    assert not tracker.complete(first.job_id, first.lease_token, {})
    assert not tracker.heartbeat(first.job_id, first.lease_token)
    assert tracker.fail(second.job_id, second.lease_token, 'invalid_pdf', 'Invalid PDF', retryable=False)
    with db.session() as s:
        assert s.get(Job, first.job_id).status == 'failed'
        assert s.query(Attempt).count() == 2


def test_cancel_prevents_completion_and_persists(env):
    _, tracker, _ = env
    p = Principal('alice', 'alpha', 'member')
    result = submit(tracker)
    claim = tracker.claim('worker')
    assert tracker.cancel(p, claim.job_id)['status'] == 'cancel_requested'
    assert not tracker.complete(claim.job_id, claim.lease_token, {})
    assert tracker.cancelled(claim.job_id, claim.lease_token)
    assert tracker.finish_cancel(claim.job_id, claim.lease_token)
    assert tracker.get_job(p, claim.job_id)['status'] == 'cancelled'


def test_failure_budget_does_not_loop_forever(env):
    db, tracker, _ = env
    submit(tracker)
    for i in range(3):
        claim = tracker.claim('worker')
        assert claim
        assert tracker.fail(claim.job_id, claim.lease_token, 'temporary', 'Temporary failure')
        with db.session() as s:
            s.get(Job, claim.job_id).available_at = utcnow() - timedelta(seconds=1)
    assert tracker.claim('worker') is None
    with db.session() as s:
        assert s.get(Job, claim.job_id).status == 'failed'


def test_concurrent_workers_only_claim_once(env):
    db, tracker, _ = env
    if db.engine.dialect.name != 'postgresql':
        pytest.skip('Real PostgreSQL locking test; set OCR_TEST_DATABASE_URL')
    submit(tracker)
    with ThreadPoolExecutor(max_workers=8) as pool:
        claims = list(pool.map(tracker.claim, [f'w{i}' for i in range(8)]))
    assert sum(c is not None for c in claims) == 1
