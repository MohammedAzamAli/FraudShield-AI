"""Read-only Firebase account diagnostic; never prints secrets or tokens.
Run from backend: python check_firebase_user.py --email your@example.com
"""
import argparse
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name('.env'))
parser = argparse.ArgumentParser(description='Check Firebase email verification status')
parser.add_argument('--email', required=True, help='Email address of your Firebase test user')
args = parser.parse_args()

credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', '')
project_id = os.getenv('FIREBASE_PROJECT_ID', '')
if not project_id:
    raise SystemExit('FIREBASE_PROJECT_ID missing from backend/.env')
if not credentials_path or not Path(credentials_path).is_file():
    raise SystemExit('Credentials file not found. Check GOOGLE_APPLICATION_CREDENTIALS in backend/.env (use forward slashes).')

import firebase_admin
from firebase_admin import credentials, auth
if not firebase_admin._apps:
    firebase_admin.initialize_app(credentials.ApplicationDefault(), {'projectId': project_id})
try:
    user = auth.get_user_by_email(args.email.strip().lower())
except auth.UserNotFoundError:
    raise SystemExit('No matching Firebase account in this project. Confirm project ID and email.')
print('Firebase account found: True')
print('Email verified:', user.email_verified)
print('Account disabled:', user.disabled)
print('Next: verify email and sign in to FraudShield AI; then promote from backend if needed.')
