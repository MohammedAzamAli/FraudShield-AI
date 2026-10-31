# FraudShield AI v8 — Firebase Authentication Integration

This package is based on the working v7 application. Firebase is **opt-in** through `AUTH_MODE=firebase`. Existing local-auth backend tests still work in the default local mode.

## 1. Firebase console

In the **separate FraudShield AI Firebase project**:
- Enable **Authentication > Sign-in method > Email/Password**, and **Google**.
- Under **Authentication > Settings > Authorized domains**, add `localhost` if necessary for your local browser. Use exactly the domain serving your frontend.
- Register a Web app. Copy its web configuration (API key, auth domain, project ID, app ID), but **do not share your secret service account key**.
- Download a service account key from **Project settings > Service accounts > Generate new private key** if your backend is running locally. Store it outside the repository, e.g. `C:/secure/fraudshield-firebase-admin.json`. Prefer workload identity on production cloud hosts.

## 2. Backend (PowerShell)

Open a terminal at the `backend` directory:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `backend/.env`:

```dotenv
AUTH_MODE=firebase
FIREBASE_PROJECT_ID=your-project-id
GOOGLE_APPLICATION_CREDENTIALS=C:/secure/fraudshield-firebase-admin.json
FRONTEND_ORIGINS=http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5174,http://localhost:5174
```

Start the API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Expected API docs: http://127.0.0.1:8000/docs. Do not interpret `GET /` returning 404 as failure.

**Existing v7 database migration:** This is an academic prototype; the Firebase IDs are stored as `fb:<uid>` in the existing `users` table (no schema migration is required). Existing local users will not be automatically linked. If their email collides with a Firebase user, login is rejected until an administrator handles migration. Use a backed-up copy of your v7 database.

## 3. Frontend (second PowerShell terminal)

From `frontend`:

```powershell
Copy-Item .env.example .env.local
npm install
npm run dev
```

Edit `.env.local` with actual Firebase **web config** (not a service account):

```dotenv
VITE_API_URL=http://127.0.0.1:8000
VITE_FIREBASE_API_KEY=YOUR_WEB_API_KEY
VITE_FIREBASE_AUTH_DOMAIN=YOUR_PROJECT.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=YOUR_PROJECT
VITE_FIREBASE_APP_ID=YOUR_WEB_APP_ID
```

Open the Vite local URL and choose **Security & Login**. Create an account or use Google Sign-In. Email/password users must click the email verification link, then sign in or refresh their credentials. The backend provisions the account on the first verified request. Firebase access tokens are refreshed by the Firebase SDK and React updates the session using `onIdTokenChanged`.

## 4. Roles (important)

New Firebase accounts start with **viewer** permissions. Users cannot select their own roles. After an account has signed in with a verified email, from the `backend` directory run:

```powershell
.\.venv\Scripts\python.exe promote_firebase_user.py --email analyst@example.com --role analyst
.\.venv\Scripts\python.exe promote_firebase_user.py --email admin@example.com --role admin
```

Use actual test account emails, ideally separate analyst and administrator accounts. Re-log in / reload after role changes. The backend checks the stored role on each authenticated request. Roles:

- `viewer`: login and research explanations; no case edits, user directory, or report export.
- `analyst`: assignments, case changes, audit history, user directory.
- `admin`: analyst features and authenticated CSV reports.

In Firebase mode, the old local `/api/auth/register` and `/api/auth/login` endpoints are disabled, and old `X-Admin-Key` modification/export endpoints are disabled. The v7 `/api/auth/me` endpoint now accepts a Firebase ID token.

## 5. End-to-end checks

1. Create a verified email/password user. Visit Security & Login; the profile should show `VIEWER`.
2. Try `Investigations > Review` while viewer; it should return `403`.
3. Promote the viewer to analyst from the trusted backend, then reload/sign in again. Case reviews should be permitted and appear in the audit log.
4. Promote a separate verified account to admin and test Reports CSV export.
5. Test Google Sign-In and logout.
6. Test incorrect/expired token; `/api/auth/me` should return `401`. Attempt an unverified email/password login; backend should return `403`.

## Security limits before real production use

- **Important:** This phase does NOT protect every existing v7 public route. Transaction history, cases list, analytics and WebSocket broadcasts remain accessible as academic sandbox data. Do **not** put real financial records, real UPI identifiers, personal information, or confidential content into this project. They must be protected before real-world deployment.
- Do not trust frontend role flags. Privileged changes are verified against the server database.
- Don't commit `.env`, `.env.local`, Firebase Admin private keys, SQLite files or user data. The frontend Firebase web API key is a public identifier and must be used with correct Firebase configuration and security rules; it is not the Admin secret.
- Keep `AUTH_MODE=firebase` in production and HTTPS on all production URLs. For robust protection, also add rate limiting, CSRF-aware cookie design if cookies are introduced, account migration, monitoring and integration testing.

## Verification performed here

- Existing backend tests plus Firebase mock-verification tests: **18 passed**.
- Python syntax compilation: **passed**.
- Live Firebase Admin SDK token test: **not possible** without your Firebase credentials and local configuration.
- Frontend production build: **not verified**; npm Firebase package was unavailable in the local offline cache. Run `npm install` then `npm run build` on your laptop.
