from pathlib import Path as _EnvPath
from dotenv import load_dotenv
load_dotenv(_EnvPath(__file__).resolve().parents[1]/".env")
"""FraudShield sandbox API. No real UPI payments or bank connections."""
import json,os,re,io,csv,hmac
from uuid import uuid4
from datetime import datetime,timezone
from pathlib import Path
from collections import Counter
from functools import lru_cache
from fastapi import FastAPI,Depends,HTTPException,WebSocket,WebSocketDisconnect,Header
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel,Field
from sqlalchemy.orm import Session
from sqlalchemy import select
from .db import Base,engine,SessionLocal,Transaction,User,CaseAudit,CaseAssignment

app=FastAPI(title='FraudShield AI — Sandbox',version='10.0.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:8080",
        "http://localhost:8080",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)
Base.metadata.create_all(bind=engine)
clients=[]

def db_session():
    db=SessionLocal()
    try:yield db
    finally:db.close()

class Payment(BaseModel):
    amount:float=Field(gt=0,le=1000000)
    recipient_upi:str=Field(min_length=3,max_length=100,pattern=r'^[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+$')
    typical_amount:float=Field(gt=0,le=1000000)
    recent_count:int=Field(ge=0,le=100)
    hour:int=Field(ge=0,le=23)
    new_recipient:bool

class Review(BaseModel):
    status:str=Field(pattern='^(OPEN|UNDER_REVIEW|CLOSED)$')
    note:str=Field(default='',max_length=500)

class QRRequest(BaseModel):
    uri:str=Field(min_length=5,max_length=2000)

def serialize(t):
    return {'id':t.id,'timestamp':t.timestamp.isoformat() if t.timestamp else None,'amount':t.amount,'recipient_upi':t.recipient_upi,'typical_amount':t.typical_amount,'recent_count':t.recent_count,'hour':t.hour,'new_recipient':t.new_recipient,'score':t.score,'risk':t.risk,'decision':t.decision,'reasons':json.loads(t.reasons),'model':t.model,'review_status':t.review_status,'reviewer_note':t.reviewer_note}

def baseline(p):
    score=0;reasons=[]
    if p.amount>5*p.typical_amount:score+=35;reasons.append('Amount exceeds five times the typical payment')
    if p.new_recipient:score+=25;reasons.append('Recipient has no previous payment history')
    if p.hour<5:score+=15;reasons.append('Payment initiated during overnight hours')
    if p.recent_count>=5:score+=25;reasons.append('Five or more payments in the last hour')
    risk='HIGH' if score>=70 else 'MEDIUM' if score>=40 else 'LOW'
    decision={'HIGH':'HOLD_FOR_REVIEW','MEDIUM':'WARN','LOW':'APPROVED_SIMULATION'}[risk]
    return score,reasons,risk,decision

@app.get('/api/health')
def health():return {'status':'ok','mode':'sandbox','model':'rules-baseline-v1','storage':'persistent','version':'10.0.0'}

@app.post('/api/analyze')
async def analyze(p:Payment,db:Session=Depends(db_session)):
    score,reasons,risk,decision=baseline(p)
    t=Transaction(id=str(uuid4()),timestamp=datetime.now(timezone.utc),**p.model_dump(),score=score,reasons=json.dumps(reasons),risk=risk,decision=decision,model='rules-baseline-v1',review_status='OPEN' if risk=='HIGH' else 'CLOSED')
    db.add(t);db.commit();db.refresh(t)
    result=serialize(t)
    for ws in clients[:]:
        try:await ws.send_json({'event':'transaction','data':result})
        except Exception:clients.remove(ws)
    return result

@app.get('/api/transactions')
def transactions(limit:int=100,db:Session=Depends(db_session)):
    if not 1<=limit<=500:raise HTTPException(422,'limit must be 1-500')
    return [serialize(x) for x in db.execute(select(Transaction).order_by(Transaction.timestamp.desc()).limit(limit)).scalars().all()]

@app.get('/api/summary')
def summary(db:Session=Depends(db_session)):
    items=db.execute(select(Transaction)).scalars().all();c=Counter(t.risk for t in items)
    return {'total':len(items),'high':c['HIGH'],'medium':c['MEDIUM'],'low':c['LOW'],'open_cases':sum(t.review_status=='OPEN' for t in items),'total_volume':round(sum(t.amount for t in items),2)}

@app.get('/api/cases')
def cases(db:Session=Depends(db_session)):
    return [serialize(t) for t in db.execute(select(Transaction).where(Transaction.risk=='HIGH').order_by(Transaction.timestamp.desc())).scalars().all()]

@app.patch('/api/cases/{transaction_id}')
def review_case(transaction_id:str,review:Review,db:Session=Depends(db_session),x_admin_key:str|None=Header(default=None)):
    from .security import firebase_mode
    if firebase_mode():raise HTTPException(403,'Legacy admin-key endpoint disabled in Firebase mode')
    expected=os.getenv('ADMIN_API_KEY')
    if not expected or not x_admin_key or not hmac.compare_digest(x_admin_key,expected):raise HTTPException(403,'Configure ADMIN_API_KEY and provide X-Admin-Key to review cases')
    t=db.get(Transaction,transaction_id)
    if not t or t.risk!='HIGH':raise HTTPException(404,'Case not found')
    t.review_status=review.status;t.reviewer_note=review.note;db.commit();db.refresh(t)
    return serialize(t)

@app.post('/api/qr/inspect')
def inspect_qr(req:QRRequest):
    from urllib.parse import urlsplit,parse_qs
    u=urlsplit(req.uri)
    if u.scheme.lower()!='upi' or u.netloc.lower()!='pay':raise HTTPException(422,'Not a UPI pay URI')
    args=parse_qs(u.query,keep_blank_values=True)
    payee=args.get('pa',[''])[0]
    if not re.fullmatch(r'[A-Za-z0-9._-]+@[A-Za-z0-9.-]+',payee):raise HTTPException(422,'Invalid payee VPA')
    amount=args.get('am',[''])[0]
    warnings=[]
    if amount:
        try:
            a=float(amount)
            if not 0<a<=1000000:raise ValueError()
        except ValueError:raise HTTPException(422,'Invalid amount')
    if not args.get('pn',[''])[0]:warnings.append('Payee name is missing; independently verify the recipient')
    return {'payee':payee,'payee_name':args.get('pn',[''])[0],'amount':amount or None,'warnings':warnings,'verified':False,'note':'QR parsing cannot establish whether a recipient is legitimate.'}

@app.websocket('/ws/alerts')
async def alerts(ws:WebSocket):
    # Public read-only stream of sandbox transactions; do not expose real financial data.
    await ws.accept();clients.append(ws)
    try:
        while True:await ws.receive_text()
    except WebSocketDisconnect:pass
    finally:
        if ws in clients:clients.remove(ws)

@app.get('/api/model/metrics')
def model_metrics():
    path=Path(__file__).resolve().parents[1]/'models'/'metrics.json'
    if not path.exists():raise HTTPException(503,'Train the model first with python ml/train.py')
    return json.loads(path.read_text())

@app.get('/api/insights')
def insights(db:Session=Depends(db_session)):
    items=db.execute(select(Transaction).order_by(Transaction.timestamp.desc()).limit(500)).scalars().all()
    by_hour=Counter(t.hour for t in items)
    return {'hourly':[{'hour':h,'count':by_hour[h]} for h in range(24)],'risk':dict(Counter(t.risk for t in items)),'recent_high':[serialize(t) for t in items if t.risk=='HIGH'][:8]}

@app.post('/api/ml/sandbox-predict')
def sandbox_predict(p: Payment):
    """Research-only ML output. Not used to authorize or block payments."""
    import numpy as np
    bundle = load_sandbox_model()
    x = np.array([[p.amount, p.typical_amount, p.recent_count, p.hour,
                   int(p.new_recipient), p.amount / p.typical_amount]], dtype=float)
    probability = float(bundle['model'].predict_proba(x)[0, 1])
    baseline_score, reasons, _, _ = baseline(p)
    return {
        'model': bundle['version'],
        'estimated_synthetic_label_probability': round(probability, 4),
        'research_threshold': 0.15,
        'research_flag': probability >= 0.15,
        'features_used': bundle['features'],
        'baseline_score': baseline_score,
        'baseline_reasons': reasons,
        'warning': 'Research-only score trained on synthetic labels. Not a real-world fraud probability or payment decision.'
    }

@app.get('/api/ml/sandbox-metrics')
def sandbox_metrics():
    path = Path(__file__).resolve().parents[1] / 'models' / 'sandbox_metrics.json'
    if not path.exists():
        raise HTTPException(503, 'Run python ml/train_sandbox.py first')
    return json.loads(path.read_text())


@lru_cache(maxsize=1)
def load_sandbox_model():
    """Load a trusted local artifact once instead of unpickling on every request."""
    import joblib
    path = Path(__file__).resolve().parents[1] / 'models' / 'sandbox_pipeline.joblib'
    if not path.exists():
        raise HTTPException(503, 'Run python ml/train_sandbox.py to create the sandbox model')
    return joblib.load(path)

@app.get('/api/analytics')
def analytics(db:Session=Depends(db_session)):
    """Aggregated sandbox analytics, with no recipient identifiers in the response."""
    items=db.execute(select(Transaction)).scalars().all()
    by_day={}
    for t in items:
        day=t.timestamp.date().isoformat()
        entry=by_day.setdefault(day,{'date':day,'total':0,'high':0,'medium':0,'low':0,'volume':0.0})
        entry['total']+=1
        entry[t.risk.lower()]+=1
        entry['volume']+=t.amount
    daily=sorted(by_day.values(),key=lambda x:x['date'])[-30:]
    for entry in daily:entry['volume']=round(entry['volume'],2)
    risks=Counter(t.risk for t in items)
    return {'daily':daily,'risk_distribution':{'HIGH':risks['HIGH'],'MEDIUM':risks['MEDIUM'],'LOW':risks['LOW']},
            'total':len(items),'total_volume':round(sum(t.amount for t in items),2),
            'average_risk_score':round(sum(t.score for t in items)/len(items),1) if items else 0,
            'review_open':sum(t.review_status=='OPEN' for t in items),
            'review_in_progress':sum(t.review_status=='UNDER_REVIEW' for t in items),
            'note':'Aggregated synthetic sandbox transactions only; risk scores are rules-based.'}

@app.get('/api/admin/transactions.csv')
def export_transactions(db:Session=Depends(db_session),x_admin_key:str|None=Header(default=None)):
    """Admin-only export for academic investigation and testing."""
    from .security import firebase_mode
    if firebase_mode():raise HTTPException(403,'Legacy admin-key endpoint disabled in Firebase mode')
    expected=os.getenv('ADMIN_API_KEY')
    if not expected or not x_admin_key or not hmac.compare_digest(x_admin_key,expected):
        raise HTTPException(403,'Admin key required')
    buf=io.StringIO()
    writer=csv.writer(buf)
    writer.writerow(['id','timestamp','recipient_upi','amount','risk_score','risk','decision','review_status','reviewer_note'])
    for t in db.execute(select(Transaction).order_by(Transaction.timestamp.desc())).scalars():
        # Protect CSV viewers against formula injection from user-supplied text.
        def safe(value):
            if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@')):return "'"+value
            return value
        writer.writerow([safe(v) for v in [t.id,t.timestamp.isoformat(),t.recipient_upi,t.amount,t.score,t.risk,t.decision,t.review_status,t.reviewer_note]])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="fraudshield_sandbox_transactions.csv"'})

# Version 7 extensions retain the earlier public sandbox API for compatibility.
from .advanced import router as advanced_router
app.include_router(advanced_router)

from .copilot import router as copilot_router
app.include_router(copilot_router)
