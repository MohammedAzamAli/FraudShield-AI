"""Role-based authentication for local academic sandbox. Never embed secrets in the frontend."""
import os
from datetime import datetime,timezone,timedelta
from uuid import uuid4
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from fastapi import Depends,HTTPException
from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import User,SessionLocal

bearer=HTTPBearer(auto_error=False)
passwords=PasswordHasher()

def secret():
    value=os.getenv('JWT_SECRET','')
    if len(value)<32:raise HTTPException(503,'JWT_SECRET must be configured (at least 32 characters)')
    return value

def verify_password(raw,stored):
    try:return bool(passwords.verify(stored,raw))
    except (VerifyMismatchError,VerificationError,ValueError):return False

def db_session():
    session=SessionLocal()
    try:yield session
    finally:session.close()

def firebase_mode():
    return os.getenv('AUTH_MODE', 'local').strip().lower() == 'firebase'


def _firebase_admin_app():
    """Firebase Admin uses GOOGLE_APPLICATION_CREDENTIALS or workload identity."""
    try:
        import firebase_admin
        from firebase_admin import credentials
    except ImportError as exc:
        raise HTTPException(503, 'firebase-admin is not installed') from exc
    if not firebase_admin._apps:
        project_id = os.getenv('FIREBASE_PROJECT_ID')
        if not project_id:
            raise HTTPException(503, 'FIREBASE_PROJECT_ID must be set')
        firebase_admin.initialize_app(credentials.ApplicationDefault(), {'projectId':project_id})
    return firebase_admin.get_app()


def verify_firebase_user(id_token: str, db: Session):
    """Verify a Firebase ID token, provision only viewer permissions by default."""
    from firebase_admin import auth
    _firebase_admin_app()
    try:
        claims = auth.verify_id_token(id_token, check_revoked=True)
    except (ValueError, auth.InvalidIdTokenError, auth.ExpiredIdTokenError,
            auth.RevokedIdTokenError, auth.UserDisabledError) as exc:
        raise HTTPException(401, 'Invalid, expired or revoked Firebase token') from exc
    except Exception as exc:
        # Fail closed for temporary Firebase verification failures.
        raise HTTPException(503, 'Firebase token verification unavailable') from exc
    uid = claims.get('uid')
    if not uid or claims.get('firebase', {}).get('sign_in_provider') in (None, 'anonymous'):
        raise HTTPException(401, 'Authenticated Firebase user required')
    verified_email = claims.get('email', '').strip().lower()
    if not verified_email or not claims.get('email_verified', False):
        raise HTTPException(403, 'Verify your Firebase email before accessing FraudShield')
    user_id = 'fb:' + uid
    user = db.get(User, user_id)
    if not user:
        owner = db.execute(select(User).where(User.email==verified_email)).scalar_one_or_none()
        if owner:
            raise HTTPException(409, 'Email already belongs to another account. Contact administrator for migration.')
        user = User(id=user_id,email=verified_email,
                    display_name=(claims.get('name') or verified_email.split('@')[0])[:100],
                    password_hash='FIREBASE_MANAGED_NO_LOCAL_PASSWORD',role='viewer')
        db.add(user)
        db.commit()
        db.refresh(user)
    elif user.email != verified_email:
        raise HTTPException(409, 'Firebase email has changed; contact an administrator')
    return user


def current_user(creds:HTTPAuthorizationCredentials|None=Depends(bearer),db:Session=Depends(db_session)):
    if not creds:raise HTTPException(401,'Login required',headers={'WWW-Authenticate':'Bearer'})
    if firebase_mode():
        return verify_firebase_user(creds.credentials,db)
    try:
        data=jwt.decode(creds.credentials,secret(),algorithms=['HS256'],options={'require':['exp','sub']})
        user=db.get(User,data['sub'])
        if not user:raise ValueError('Unknown user')
        return user
    except (jwt.InvalidTokenError,ValueError,KeyError):raise HTTPException(401,'Invalid or expired login')

def require_role(*roles):
    def check(user:User=Depends(current_user)):
        if user.role not in roles:raise HTTPException(403,'Insufficient permissions')
        return user
    return check

def access_token(user):
    now=datetime.now(timezone.utc)
    return jwt.encode({'sub':user.id,'iat':now,'exp':now+timedelta(hours=4)},secret(),algorithm='HS256')

def public_user(user):
    return {'id':user.id,'email':user.email,'display_name':user.display_name,'role':user.role}
