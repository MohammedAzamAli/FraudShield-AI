# FraudShield AI v9 — Firebase verification and administrator onboarding

This is a full copy of FraudShield AI v8 with targeted authentication improvements, not a replacement for the existing UPI simulator, ML research, QR inspection, investigations, analytics or reports.

## Changes

- Email/password registration still sends Firebase verification email.
- A signed-in but unverified user now sees **Resend verification email**, **I verified my email**, and **Log out**.
- The resend action has a one-minute in-page throttle to discourage repeat requests. Firebase's own rate limits still apply.
- The verification refresh reloads the Firebase user and requests a fresh ID token. `App.jsx` re-checks `/api/auth/me` on token changes.
- The UI distinguishes a Firebase sign-in from a backend-authenticated `viewer`, `analyst`, or `admin` session.
- Backend errors from `/api/auth/me` appear in the interface, instead of only browser console logs.
- `backend/check_firebase_user.py` checks the authoritative Firebase account's email verification and disabled status. It prints no keys or tokens.
- The existing `promote_firebase_user.py` script still promotes only a backend-provisioned `fb:` account. Newly verified users are **viewer** by default.
- FastAPI's reported version is 9.0.0. All existing fraud-analysis components are preserved.

## 1 — Configure Firebase Admin credentials

Use `backend/.env`, **not** only `.env.example`:

```env
AUTH_MODE=firebase
FIREBASE_PROJECT_ID=your-firebase-project-id
GOOGLE_APPLICATION_CREDENTIALS=C:/Users/YOUR_USERNAME/firebase-secrets/your-admin-service-account.json
FRONTEND_ORIGINS=http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5174,http://localhost:5174
```

Keep the admin JSON **outside the project and GitHub**. On Windows use forward slashes and no double quotes: an input like `"C:\\...\\fraudshield..."` can be misinterpreted by dotenv because `\\f` becomes a form-feed character. Never use the JSON file in React.

Set `frontend/.env.local`:

```env
VITE_API_URL=http://127.0.0.1:8000
VITE_FIREBASE_API_KEY=from-your-firebase-web-app
VITE_FIREBASE_AUTH_DOMAIN=from-your-firebase-web-app
VITE_FIREBASE_PROJECT_ID=from-your-firebase-web-app
VITE_FIREBASE_APP_ID=from-your-firebase-web-app
```

These four web configuration values must come from the *same Firebase project*. Add 127.0.0.1 or localhost as an authorized domain for Google sign-in if needed.

## 2 — Run locally

Backend terminal, from `backend/`:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Frontend terminal, from `frontend/`:

```powershell
npm ci
npm run dev
```

Open the Vite local URL. Keep v8 backed up separately. Do not copy old `.env` if its credentials or Firebase Project ID refer to a different project.

## 3 — Email verification and login

1. Register with a **test** email and password. Firebase will send a verification email.
2. While logged in, open **Security & Login → Resend verification email** if needed.
3. Click the verification link in the inbox (check spam too).
4. Return to Security & Login and click **I verified my email**, or sign out and sign in again.
5. Confirm backend logs show `GET /api/auth/me` → `200 OK`. Your assigned role should initially be **VIEWER**.

A Firebase frontend sign-in does **not** mean FastAPI has granted access. The backend verifies a signed ID token and requires a verified email. Common statuses: **401** no/invalid token, **403** email unverified or insufficient role, **503** Admin SDK credentials/service unavailable.

## 4 — Diagnose account safely

From `backend/`:

```powershell
.\.venv\Scripts\python.exe -c "from dotenv import dotenv_values; import os; p=dotenv_values('.env').get('GOOGLE_APPLICATION_CREDENTIALS'); print('Exists:',os.path.isfile(p) if p else False)"
.\.venv\Scripts\python.exe check_firebase_user.py --email YOUR_TEST_EMAIL
```

Expected: `Firebase account found: True`, `Email verified: True`, `Account disabled: False`.

The diagnostic script verifies status in Firebase itself; it does not add users to the app database. The backend user profile is provisioned after a **verified** user signs in and successfully requests `/api/auth/me`.

## 5 — Assign admin / analyst after provision

Once `/api/auth/me` returns 200 at least once for the verified user:

```powershell
.\.venv\Scripts\python.exe promote_firebase_user.py --email YOUR_TEST_EMAIL --role admin
```

Use `analyst` to assign analyst privileges. Restart the browser session / sign in again to get the latest role. Do not grant roles by editing React or adding client-controlled claims. This is a trusted backend terminal operation intended for a local academic environment; protect backend/DB access.

## 6 — Tests and remaining limitations

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
cd ..\frontend
npm run build
npm audit
```

Validation in the packaging environment: 18 backend tests passed; Python compiled. Frontend build could not be executed because the Firebase npm package was unavailable from its offline cache. Run `npm ci` and `npm run build` on Windows before claiming complete integration.

The existing public transaction APIs and WebSocket are still intended for **synthetic sandbox data only** and are not all secured by Firebase. Never deploy publicly with real sensitive data until those routes, rate limits, logging, and privacy controls are hardened. Research ML results are synthetic and not proof of production UPI fraud detection.

## Safety reminder

A password appeared in an earlier screenshot. If that was an actual password, rotate it immediately. Never share Firebase Admin JSON private keys, access tokens, or real passwords in screenshots, logs, Git or chat.
