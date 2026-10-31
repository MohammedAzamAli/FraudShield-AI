"""Additional sandbox capabilities: RBAC, explainable research ML and QR image inspection."""
import os,io,json,re
from datetime import datetime,timezone
from uuid import uuid4
from pathlib import Path
from fastapi import APIRouter,Depends,HTTPException,UploadFile,File
from pydantic import BaseModel,Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import User,Transaction,CaseAudit,CaseAssignment
from .security import passwords,verify_password,db_session,require_role,current_user,access_token,public_user,firebase_mode

router=APIRouter(prefix='/api')
class Register(BaseModel):
    email:str=Field(min_length=5,max_length=255)
    password:str=Field(min_length=12,max_length=128)
    display_name:str=Field(min_length=2,max_length=100)
class Login(BaseModel):
    email:str
    password:str
class CaseUpdate(BaseModel):
    status:str=Field(pattern='^(OPEN|UNDER_REVIEW|CLOSED)$')
    note:str=Field(min_length=3,max_length=500)
class Assign(BaseModel):
    user_id:str
class ExplainRequest(BaseModel):
    amount:float=Field(gt=0,le=1000000)
    recipient_upi:str=Field(min_length=3,max_length=100)
    typical_amount:float=Field(gt=0,le=1000000)
    recent_count:int=Field(ge=0,le=100)
    hour:int=Field(ge=0,le=23)
    new_recipient:bool

@router.post('/auth/register',status_code=201)
def register(body:Register,db:Session=Depends(db_session)):
    if firebase_mode():raise HTTPException(403,'Use Firebase registration')
    email=body.email.strip().lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):raise HTTPException(422,'Invalid email')
    if db.execute(select(User).where(User.email==email)).scalar_one_or_none():raise HTTPException(409,'Email already registered')
    user=User(id=str(uuid4()),email=email,display_name=body.display_name.strip(),password_hash=passwords.hash(body.password),role='analyst')
    db.add(user);db.commit()
    return {'message':'Account registered as analyst','user':public_user(user)}

@router.post('/auth/login')
def login(body:Login,db:Session=Depends(db_session)):
    if firebase_mode():raise HTTPException(403,'Use Firebase login')
    user=db.execute(select(User).where(User.email==body.email.strip().lower())).scalar_one_or_none()
    if not user or not verify_password(body.password,user.password_hash):raise HTTPException(401,'Invalid credentials')
    return {'access_token':access_token(user),'token_type':'bearer','user':public_user(user)}

@router.get('/auth/me')
def me(user=Depends(current_user)):return public_user(user)

@router.get('/users')
def users(admin=Depends(require_role('admin','analyst')),db:Session=Depends(db_session)):
    return [public_user(u) for u in db.execute(select(User).order_by(User.display_name)).scalars()]

@router.get('/cases/{transaction_id}/audit')
def audit(transaction_id:str,user=Depends(require_role('admin','analyst')),db:Session=Depends(db_session)):
    return [{'id':a.id,'action':a.action,'actor_id':a.actor_id,'previous_status':a.previous_status,'new_status':a.new_status,'note':a.note,'created_at':a.created_at.isoformat()} for a in db.execute(select(CaseAudit).where(CaseAudit.transaction_id==transaction_id).order_by(CaseAudit.created_at)).scalars()]

@router.get('/cases/assignments/all')
def assignments(user=Depends(require_role('admin','analyst')),db:Session=Depends(db_session)):
    return [{'transaction_id':a.transaction_id,'assigned_to':a.assigned_to,'assigned_by':a.assigned_by} for a in db.execute(select(CaseAssignment)).scalars()]

@router.post('/cases/{transaction_id}/assign')
def assign_case(transaction_id:str,body:Assign,actor=Depends(require_role('admin','analyst')),db:Session=Depends(db_session)):
    t=db.get(Transaction,transaction_id);target=db.get(User,body.user_id)
    if not t or t.risk!='HIGH':raise HTTPException(404,'Case not found')
    if not target or target.role not in ('admin','analyst'):raise HTTPException(422,'Choose an analyst or administrator')
    a=db.get(CaseAssignment,transaction_id)
    if not a:a=CaseAssignment(transaction_id=transaction_id,assigned_to=target.id,assigned_by=actor.id);db.add(a)
    else:a.assigned_to=target.id;a.assigned_by=actor.id;a.updated_at=datetime.now(timezone.utc)
    db.add(CaseAudit(id=str(uuid4()),transaction_id=t.id,actor_id=actor.id,action='ASSIGN',previous_status=t.review_status,new_status=t.review_status,note='Assigned to '+target.display_name))
    db.commit();return {'transaction_id':t.id,'assigned_to':target.id}

@router.patch('/cases/{transaction_id}/workflow')
def workflow(transaction_id:str,body:CaseUpdate,actor=Depends(require_role('admin','analyst')),db:Session=Depends(db_session)):
    t=db.get(Transaction,transaction_id)
    if not t or t.risk!='HIGH':raise HTTPException(404,'Case not found')
    prior=t.review_status;t.review_status=body.status;t.reviewer_note=body.note
    db.add(CaseAudit(id=str(uuid4()),transaction_id=t.id,actor_id=actor.id,action='STATUS_CHANGE',previous_status=prior,new_status=body.status,note=body.note))
    db.commit();return {'transaction_id':t.id,'status':t.review_status,'note':t.reviewer_note}

@router.post('/qr/decode-image')
async def decode_qr_image(file:UploadFile=File(...)):
    if file.content_type not in ('image/png','image/jpeg','image/webp'):raise HTTPException(415,'PNG, JPEG or WebP image required')
    data=await file.read(3_000_001)
    if len(data)>3_000_000:raise HTTPException(413,'Maximum 3 MB image')
    try:
        import cv2,numpy as np
        img=cv2.imdecode(np.frombuffer(data,dtype=np.uint8),cv2.IMREAD_COLOR)
        if img is None or img.shape[0]*img.shape[1]>12_000_000:raise ValueError('Image invalid or too large')
        decoded,_,_=cv2.QRCodeDetector().detectAndDecode(img)
        if not decoded:raise HTTPException(422,'No readable QR found')
        if not decoded.lower().startswith('upi://pay?'):raise HTTPException(422,'QR is not a UPI payment URI')
        return {'uri':decoded,'note':'Decoded QR text only; this does not verify the recipient.'}
    except HTTPException:raise
    except (ValueError,cv2.error) as exc:raise HTTPException(422,'Invalid QR image') from exc

@router.post('/ml/explain')
def explain(body:ExplainRequest,user=Depends(current_user)):
    """SHAP attribution is experimental and based on synthetic training labels."""
    import numpy as np
    import shap
    from .main import load_sandbox_model
    bundle=load_sandbox_model()
    x=np.array([[body.amount,body.typical_amount,body.recent_count,body.hour,int(body.new_recipient),body.amount/body.typical_amount]],dtype=float)
    estimator=bundle['model']
    # TreeExplainer is used against the exact trained estimator, without arbitrary risk explanations.
    explanation=shap.TreeExplainer(estimator)(x)
    vals=np.asarray(explanation.values)
    # For binary probability output some SHAP releases return n_features x n_classes.
    if vals.ndim==3: contributions=vals[0,:,1]
    elif vals.ndim==2:contributions=vals[0]
    else:raise HTTPException(503,'Unexpected SHAP attribution format')
    prob=float(estimator.predict_proba(x)[0,1])
    return {'model':bundle['version'],'estimated_synthetic_label_probability':round(prob,5),
            'contributions':[{'feature':k,'value':float(v),'input':float(x[0,i])} for i,(k,v) in enumerate(zip(bundle['features'],contributions))],
            'warning':'SHAP explains a synthetic-label research model, NOT verified UPI fraud. Contributions are relative to model baseline.'}

@router.get('/reports/transactions.csv')
def authenticated_export(actor=Depends(require_role('admin')),db:Session=Depends(db_session)):
    import csv,io
    from fastapi.responses import StreamingResponse
    buf=io.StringIO();writer=csv.writer(buf)
    writer.writerow(['id','timestamp','recipient_upi','amount','risk','score','decision','review_status'])
    def safe(v):
        if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')):return "'"+v
        return v
    for t in db.execute(select(Transaction).order_by(Transaction.timestamp.desc())).scalars():
        writer.writerow([safe(v) for v in [t.id,t.timestamp.isoformat(),t.recipient_upi,t.amount,t.risk,t.score,t.decision,t.review_status]])
    return StreamingResponse(iter([buf.getvalue()]),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="fraudshield_v7.csv"'})

@router.get('/ml/comparison')
def model_comparison():
    file=Path(__file__).resolve().parents[1]/'models'/'comparison_metrics.json'
    if not file.exists():raise HTTPException(503,'Run python ml/compare_models.py from project root')
    return json.loads(file.read_text())
