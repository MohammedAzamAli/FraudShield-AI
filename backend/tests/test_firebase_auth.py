"""Isolated tests of Firebase identity provisioning and role enforcement.
Mock signature verifier only in tests; production always uses Firebase Admin SDK.
"""
import os,sys,types
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db import Base,User
from app import security
from fastapi import HTTPException

def test_firebase_verified_user_is_viewer_by_default(monkeypatch):
    fake=types.ModuleType('firebase_admin')
    auth=types.SimpleNamespace(
        verify_id_token=lambda token,check_revoked: {'uid':'unit-123','email':'test@demo.com','email_verified':True,'firebase':{'sign_in_provider':'google.com'}},
        InvalidIdTokenError=type('InvalidIdTokenError',(Exception,),{}),
        ExpiredIdTokenError=type('ExpiredIdTokenError',(Exception,),{}),
        RevokedIdTokenError=type('RevokedIdTokenError',(Exception,),{}),
        UserDisabledError=type('UserDisabledError',(Exception,),{}),
    )
    fake.auth=auth
    monkeypatch.setitem(sys.modules,'firebase_admin',fake)
    monkeypatch.setattr(security,'_firebase_admin_app',lambda:None)
    engine=create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user=security.verify_firebase_user('token',db)
        assert user.role=='viewer'
        assert user.id=='fb:unit-123'
        assert security.verify_firebase_user('token',db).id==user.id

def test_unverified_email_rejected(monkeypatch):
    fake=types.ModuleType('firebase_admin')
    fake.auth=types.SimpleNamespace(
        verify_id_token=lambda token,check_revoked: {'uid':'test123','email':'demo@example.com','email_verified':False,'firebase':{'sign_in_provider':'password'}},
        InvalidIdTokenError=type('InvalidIdTokenError',(Exception,),{}),
        ExpiredIdTokenError=type('ExpiredIdTokenError',(Exception,),{}),
        RevokedIdTokenError=type('RevokedIdTokenError',(Exception,),{}),
        UserDisabledError=type('UserDisabledError',(Exception,),{}),
    )
    monkeypatch.setitem(sys.modules,'firebase_admin',fake)
    monkeypatch.setattr(security,'_firebase_admin_app',lambda:None)
    engine=create_engine('sqlite:///:memory:');Base.metadata.create_all(engine)
    with Session(engine) as db:
        try:security.verify_firebase_user('token',db)
        except HTTPException as exc:assert exc.status_code==403
        else:raise AssertionError('Must reject unverified email')
