"""Integration tests for v7 auth, RBAC, auditing and research explanations."""
import os
os.environ.setdefault('JWT_SECRET','TEST_ONLY_NOT_FOR_PRODUCTION_SECRET_1234567890')
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.db import SessionLocal,User
from app.security import passwords
client=TestClient(app)
PAY={'amount':45000,'recipient_upi':'test@upi','typical_amount':2000,'recent_count':6,'hour':2,'new_recipient':True}

def test_register_and_login_and_user_permissions():
    email='analyst_'+uuid4().hex[:10]+'@example.test'
    r=client.post('/api/auth/register',json={'email':email,'password':'TestPassword!12345','display_name':'QA Analyst'})
    assert r.status_code==201
    login=client.post('/api/auth/login',json={'email':email,'password':'TestPassword!12345'})
    assert login.status_code==200
    token=login.json()['access_token']
    assert client.get('/api/auth/me',headers={'Authorization':'Bearer '+token}).json()['role']=='analyst'
    assert client.get('/api/reports/transactions.csv',headers={'Authorization':'Bearer '+token}).status_code==403
    tid=client.post('/api/analyze',json=PAY).json()['id']
    assert client.patch('/api/cases/'+tid+'/workflow',json={'status':'CLOSED','note':'No authentication'}).status_code==401
    h={'Authorization':'Bearer '+token}
    assert client.patch('/api/cases/'+tid+'/workflow',headers=h,json={'status':'UNDER_REVIEW','note':'Investigating the simulated case'}).status_code==200
    audit=client.get('/api/cases/'+tid+'/audit',headers=h)
    assert audit.status_code==200 and audit.json()[-1]['action']=='STATUS_CHANGE'
    assert client.post('/api/cases/'+tid+'/assign',headers=h,json={'user_id':login.json()['user']['id']}).status_code==200
    assert client.get('/api/cases/assignments/all',headers=h).status_code==200
    assert client.post('/api/auth/login',json={'email':email,'password':'wrong'}).status_code==401

def test_bad_qr_image():
    r=client.post('/api/qr/decode-image',files={'file':('bad.txt',b'hello','text/plain')})
    assert r.status_code==415

def test_admin_export():
    email='admin_'+uuid4().hex[:10]+'@example.test'
    with SessionLocal() as db:
        u=User(id=str(uuid4()),email=email,password_hash=passwords.hash('AdminTestPassword123!'),display_name='QA Admin',role='admin')
        db.add(u);db.commit()
    token=client.post('/api/auth/login',json={'email':email,'password':'AdminTestPassword123!'}).json()['access_token']
    r=client.get('/api/reports/transactions.csv',headers={'Authorization':'Bearer '+token})
    assert r.status_code==200 and 'text/csv' in r.headers['content-type']

def test_qr_image_decoding():
    import io,qrcode
    im=qrcode.make('upi://pay?pa=merchant@upi&pn=Demo&am=500')
    data=io.BytesIO();im.save(data,format='PNG')
    response=client.post('/api/qr/decode-image',files={'file':('qr.png',data.getvalue(),'image/png')})
    assert response.status_code==200
    assert 'merchant@upi' in response.json()['uri']

def test_comparison_metrics():
    r=client.get('/api/ml/comparison')
    assert r.status_code==200
    assert 'shifted_synthetic' in r.json()['models']['Random Forest']
