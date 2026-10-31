import os
os.environ['DATABASE_URL']='sqlite:///./test_fraudshield.db'
from fastapi.testclient import TestClient
from app.main import app
client=TestClient(app)
PAY={'amount':45000,'recipient_upi':'unknown@upi','typical_amount':2000,'recent_count':6,'hour':2,'new_recipient':True}
def test_health():assert client.get('/api/health').status_code==200
def test_high_risk():
    r=client.post('/api/analyze',json=PAY)
    assert r.status_code==200
    assert r.json()['risk']=='HIGH'
    assert r.json()['score']==100
def test_bad_input():assert client.post('/api/analyze',json={**PAY,'amount':-5}).status_code==422
def test_history():assert isinstance(client.get('/api/transactions').json(),list)
def test_case_requires_admin():
    tid=client.post('/api/analyze',json=PAY).json()['id']
    assert client.patch('/api/cases/'+tid,json={'status':'CLOSED','note':'demo'}).status_code==403
def test_qr():
    r=client.post('/api/qr/inspect',json={'uri':'upi://pay?pa=test@upi&pn=Test&am=100'})
    assert r.status_code==200 and r.json()['verified'] is False

def test_sandbox_ml_prediction():
    r=client.post('/api/ml/sandbox-predict',json=PAY)
    assert r.status_code==200
    body=r.json()
    assert 0<=body['estimated_synthetic_label_probability']<=1
    assert 'warning' in body

def test_sandbox_ml_metrics():
    r=client.get('/api/ml/sandbox-metrics')
    assert r.status_code==200
    assert r.json()['dataset']=='generated sandbox scenarios'
