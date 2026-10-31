"""One-time admin creation; execute from backend directory after setting ADMIN_EMAIL and ADMIN_PASSWORD."""
import os
from uuid import uuid4
from sqlalchemy import select
from app.db import Base,engine,SessionLocal,User
from app.security import passwords
email=os.environ.get('ADMIN_EMAIL','').strip().lower()
password=os.environ.get('ADMIN_PASSWORD','')
if not email or len(password)<12:raise SystemExit('Set ADMIN_EMAIL and ADMIN_PASSWORD (12+ characters) first')
Base.metadata.create_all(bind=engine)
with SessionLocal() as db:
    if db.execute(select(User).where(User.email==email)).scalar_one_or_none():raise SystemExit('User already exists; not modifying roles')
    db.add(User(id=str(uuid4()),email=email,display_name='Sandbox Administrator',password_hash=passwords.hash(password),role='admin'))
    db.commit()
print('Administrator created. Clear ADMIN_PASSWORD from terminal environment when finished.')
