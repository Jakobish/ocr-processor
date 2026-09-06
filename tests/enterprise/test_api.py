import io
import sys
from pathlib import Path
import pytest
import fitz
from fastapi.testclient import TestClient
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from enterprise.api import create_app
from enterprise.settings import EnterpriseSettings
from enterprise.database import Database, Base
from enterprise.identity import Principal


class Identity:
    def authenticate(self, token, tenant_id=None):
        people = {'alice': Principal('alice','alpha','member'), 'bob': Principal('bob','alpha','member'), 'admin': Principal('admin','alpha','admin'), 'owner': Principal('owner','alpha','owner'), 'outsider': Principal('eve','beta','owner')}
        p = people.get(token)
        return p if p and (not tenant_id or tenant_id == p.tenant_id) else None


@pytest.fixture
def client(tmp_path):
    settings = EnterpriseSettings(database_url=f'sqlite:///{tmp_path}/api.db', storage_root=tmp_path/'storage')
    db = Database(settings.database_url)
    Base.metadata.create_all(db.engine)
    app = create_app(settings=settings, database=db, identity=Identity())
    with TestClient(app) as client:
        yield client
    db.engine.dispose()


def headers(user='alice'):
    return {'Authorization': 'Bearer '+user}


def pdf():
    doc=fitz.open()
    page=doc.new_page()
    page.insert_text((72,72),'Durable OCR document')
    data=doc.tobytes()
    doc.close()
    return data


def upload(client, user='alice'):
    r=client.post('/api/v1/uploads',headers=headers(user),files={'file':('report.pdf',pdf(),'application/pdf')})
    assert r.status_code==201, r.text
    return r.json()['id']


def batch(client,user='alice'):
    id=upload(client,user)
    r=client.post('/api/v1/batches',headers={**headers(user),'Idempotency-Key':id},json={'upload_ids':[id],'mode':'cli','language':'heb+eng'})
    assert r.status_code==202,r.text
    return r.json()


def test_missing_identity_denied_and_health_available(client):
    assert client.get('/health/live').status_code==200
    assert client.get('/api/v1/jobs').status_code==401


def test_submission_actual_state_no_simulated_success(client):
    b=batch(client)
    j=b['jobs'][0]
    assert j['status']=='queued'
    assert j['artifacts']==[]
    assert client.get('/api/v1/jobs/'+j['id'],headers=headers()).json()['status']=='queued'
    assert client.get('/api/v1/jobs/'+j['id']+'/artifacts/pdf',headers=headers()).status_code==404


def test_all_job_routes_tenant_and_member_isolation(client):
    b=batch(client)
    id=b['jobs'][0]['id']
    for user in ['bob','outsider']:
        for endpoint in [f'/jobs/{id}',f'/jobs/{id}/events',f'/jobs/{id}/artifacts/pdf',f'/batches/{b["id"]}',f'/batches/{b["id"]}/archive']:
            assert client.get('/api/v1'+endpoint,headers=headers(user)).status_code==404
        assert client.post(f'/api/v1/jobs/{id}/cancel',headers=headers(user)).status_code==404
        assert client.delete(f'/api/v1/jobs/{id}',headers=headers(user)).status_code==404
    assert client.get(f'/api/v1/jobs/{id}',headers=headers('admin')).status_code==200


def test_bad_pdf_and_external_paths_rejected(client):
    r=client.post('/api/v1/uploads',headers=headers(),files={'file':('bad.pdf',b'%PDF-1.7\nnot a PDF','application/pdf')})
    assert r.status_code==422
    assert client.post('/api/v1/batches',headers={**headers(),'Idempotency-Key':'x'},json={'input_path':'/etc/passwd','upload_ids':[]}).status_code==422


def test_cross_owner_upload_cannot_be_submitted(client):
    id=upload(client)
    r=client.post('/api/v1/batches',headers={**headers('admin'),'Idempotency-Key':'x'},json={'upload_ids':[id]})
    assert r.status_code==409


def test_cancel_and_retry_preserve_job_identity(client):
    id=batch(client)['jobs'][0]['id']
    assert client.post(f'/api/v1/jobs/{id}/cancel',headers=headers()).json()['status']=='cancelled'
    assert client.post(f'/api/v1/jobs/{id}/retry',headers=headers()).json()['status']=='queued'


def test_only_owner_manages_keys_and_raw_secret_never_listed(client):
    assert client.post('/api/v1/keys',headers=headers('admin'),json={'name':'system','scopes':['read']}).status_code==403
    r=client.post('/api/v1/keys',headers=headers('owner'),json={'name':'system','scopes':['read']})
    assert r.status_code==201,r.text
    assert r.json()['token'].startswith('ocr_')
    listed=client.get('/api/v1/keys',headers=headers('owner')).json()
    assert 'token' not in listed['items'][0]
    assert client.delete('/api/v1/keys/'+r.json()['id'],headers=headers('owner')).status_code==204


def test_openapi_declares_typed_jobs(client):
    schema=client.get('/openapi.json').json()
    assert 'JobView' in schema['components']['schemas']
    assert schema['paths']['/api/v1/batches']['post']['responses']['202']
