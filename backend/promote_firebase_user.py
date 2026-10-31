"""Run after verified Firebase user has signed in at least once.
Usage: python promote_firebase_user.py --email name@example.com --role analyst
"""
import argparse
from sqlalchemy import select
from app.db import User,SessionLocal

parser=argparse.ArgumentParser()
parser.add_argument('--email',required=True)
parser.add_argument('--role',required=True,choices=['viewer','analyst','admin'])
args=parser.parse_args()
with SessionLocal() as db:
    user=db.execute(select(User).where(User.email==args.email.strip().lower())).scalar_one_or_none()
    if user is None or not user.id.startswith('fb:'):
        raise SystemExit('Verified Firebase account not found. Sign in and verify email first.')
    user.role=args.role
    db.commit()
    print(f'Updated {user.email} to {user.role}. Sign in again if needed.')
