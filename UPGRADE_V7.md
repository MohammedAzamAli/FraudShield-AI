# FraudShield AI v7 — Advanced Major Project Upgrade

This version extends the v6 project with authenticated workflows, SHAP research explanations, QR image decoding, case assignment, audit trails, model benchmarking, and PostgreSQL/Docker deployment files.

**Important limitations**: All payment records are simulated. The ML models use synthetic labels, not verified UPI fraud. QR parsing does **not** verify any bank/payee or prove safety. The existing simulator decision remains rule-based. Do not connect real banking credentials or process actual payments.

## Setup on Windows using VS Code

**Keep v6 as a backup.** Extract this ZIP to a separate `FraudShield_AI_v7` folder. Python 3.12 and Node.js 20/22 are recommended.

Backend, VS Code terminal 1:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:JWT_SECRET = "YOUR_RANDOM_SECRET_OF_AT_LEAST_32_CHARACTERS"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

**Generate a random secret**, do not actually use the placeholder. On Windows Powershell, for example:

```powershell
$env:JWT_SECRET = (& .\.venv\Scripts\python.exe -c "import secrets;print(secrets.token_urlsafe(48))")
```

Save this secret in a private local environment variable or secure configuration for subsequent runs. A new secret invalidates previously issued tokens.

Frontend, VS Code terminal 2, starting from project root:

```powershell
cd frontend
npm ci
npm run dev
```

Browse to `http://127.0.0.1:5173` or whatever URL Vite prints. API docs: `http://127.0.0.1:8000/docs`.

## First login and administrator account

The **Security & Login** page can register analyst accounts, which can investigate sandbox cases. For initial administrator creation, stop/start a separate terminal inside `backend`, with the same `JWT_SECRET`:

```powershell
$env:ADMIN_EMAIL = "admin@example.test"
$env:ADMIN_PASSWORD = "CHANGE_TO_YOUR_OWN_LONG_PASSWORD"
.\.venv\Scripts\python.exe bootstrap_admin.py
Remove-Item Env:ADMIN_PASSWORD
```

The placeholder password is NOT suitable for actual use. Use a unique 12+ character password. Administrator creation is intentionally a separate local command; public registration cannot claim the admin role. The project uses 4-hour JWT access tokens, password hashes, and server-side roles. Logout clears the frontend's in-memory token. This is **academic security**, not a complete consumer banking identity system.

## Features to test

1. **Security & Login**: register analyst, login, logout.
2. **UPI Sandbox**: analyze a payment as before, see experimental ML comparison.
3. **ML Research**: view existing metrics, shifted synthetic model comparison, log in and press **Generate SHAP explanation**.
4. **QR Inspector**: upload a QR-code image (PNG, JPEG, WebP; up to 3 MB), inspect the decoded UPI URI. Decoding never verifies payee identity.
5. **Investigations**: sign in, add an investigation note, change status, assign a user, open the audit timeline.
6. **Reports**: sign in as admin to export CSV.
7. **Overview, Analytics and Transactions**: preserved from v6.

## Research model comparison

A pre-generated `backend/models/comparison_metrics.json` is included. Recompute it with:

```powershell
# From project root, using your backend virtual environment
.\backend\.venv\Scripts\python.exe ml\compare_models.py
```

It compares logistic regression, random forest and histogram gradient boosting on synthetic train/holdout and shifted synthetic scenarios. This is **not** real UPI fraud validation; it is intended to expose model generalization limits. GAN augmentation is not advertised as proven unless separately tested.

## Tests

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install pytest httpx qrcode[pil]
$env:JWT_SECRET = "YOUR_TEST_SECRET_LONGER_THAN_32_CHARACTERS"
.\.venv\Scripts\python.exe -m pytest -q tests
```

16 backend tests passed in the preparation environment, including auth, RBAC, case auditing, QR image decoding and prior v6 functionality. Tests create SQLite database files; avoid running on a production database.

Frontend build verification:

```powershell
cd frontend
npm ci
npm run build
```

**Frontend production build has not been verified here** due to a stalled Node dependency installation. Run it on your laptop; fix errors before deployment.

## Docker + PostgreSQL (local demonstration)

From project root:

1. Copy `.env.example` to `.env` and set **unique** long `POSTGRES_PASSWORD` and `JWT_SECRET` values. Prefer a URL-safe alphanumeric PostgreSQL password because it is interpolated inside a database connection URI.
2. Run `docker compose up --build`.
3. Visit `http://127.0.0.1:8080` for the UI and `http://127.0.0.1:8000/docs` for the API.
4. Create an administrator from the backend container using environment variables passed to the one-time bootstrap script.

Example admin bootstrap after containers start (from project directory; enter your own credentials):

```powershell
docker compose exec -e ADMIN_EMAIL=admin@example.test -e ADMIN_PASSWORD=CHANGE_THIS_LONG_PASSWORD api python bootstrap_admin.py
```

The Docker setup is intended for **local demonstration**, not Internet-facing production. Container builds and browser integration have not been exercised in the preparation environment.

## Architecture/security notes

- The public sandbox transaction and alert APIs are kept from v6 to avoid breaking your demonstration; they can expose synthetic UPI identifiers. Before production, protect all sensitive endpoints and WebSockets with session authorization.
- Case workflow and audit endpoints require signed-in `analyst` or `admin` users. Report CSV export requires `admin`.
- The legacy API-key routes remain in the backend for backward compatibility but are disabled unless an `ADMIN_API_KEY` is deliberately configured. The v7 frontend no longer relies on them.
- Current schema tables are created at startup (`create_all`). For production, use proper SQL migrations (e.g., Alembic) and reviewed role/privilege management.
- SHAP contributions explain the **experimental synthetic-label model**, not actual fraud cases. The 100% original dataset metrics remain qualified as nonrepresentative.
- As a future improvement: secure WebSocket sessions, rate limiting, refresh token rotation, email verification, TLS termination, observability, proper model version registry, and representative independently labeled datasets.
