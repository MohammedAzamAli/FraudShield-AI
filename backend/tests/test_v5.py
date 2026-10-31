import os
os.environ['DATABASE_URL']='sqlite:///./test_fraudshield.db'
from fastapi.testclient import TestClient
from app.main import app,load_sandbox_model
client=TestClient(app)

def test_analytics_shape():
    r=client.get('/api/analytics')
    assert r.status_code==200
    assert set(r.json()['risk_distribution'])=={'HIGH','MEDIUM','LOW'}

def test_export_rejects_unauthenticated():
    assert client.get('/api/admin/transactions.csv').status_code==403

def test_model_cache():
    a=load_sandbox_model()
    assert a is load_sandbox_model()
