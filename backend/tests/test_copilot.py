import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db import Base, Transaction
from app import copilot
from unittest.mock import patch
import base64, json

def test_missing_provider_key(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    with pytest.raises(HTTPException) as e: copilot._provider('openai')
    assert e.value.status_code==503

def test_unrecognized_provider_rejected():
    with pytest.raises(HTTPException) as e: copilot._provider('invalid')
    assert e.value.status_code==422

def test_transaction_context_omits_upi_identifier():
    engine=create_engine('sqlite:///:memory:');Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Transaction(id='demo-txn-1',amount=7000,recipient_upi='private@upi',typical_amount=200,
                 recent_count=3,hour=12,new_recipient=True,score=60,risk='MEDIUM',decision='WARN',
                 reasons=json.dumps(['New recipient']),model='rules',review_status='OPEN',reviewer_note=''))
        db.commit()
        data=copilot._case(db,'demo-txn-1')
        assert 'private@upi' not in json.dumps(data)
        assert 'recipient_upi' not in data
        assert data['rules_risk']=='MEDIUM'

def test_image_validation_no_external_call(monkeypatch):
    monkeypatch.setattr(copilot,'generate',lambda provider,prompt,image=None: 'Advisory only')
    img=base64.b64encode(b'\x89PNG\r\n\x1a\n'+b'123456789012').decode()
    result=copilot.screenshot(copilot.Screenshot(image_base64=img),actor=object())
    assert result['verified_fraud'] is False
    bad=base64.b64encode(b'not an image' * 3).decode()
    with pytest.raises(HTTPException) as e:
        copilot.screenshot(copilot.Screenshot(image_base64=bad),actor=object())
    assert e.value.status_code==422

def test_ask_result_advisory(monkeypatch):
    monkeypatch.setattr(copilot,'generate',lambda provider,prompt,image=None:'Review the evidence')
    result=copilot.ask(copilot.Ask(question='Explain safe next steps'),actor=object(),db=None)
    assert result['verified_fraud'] is False
    assert result['answer']=='Review the evidence'
