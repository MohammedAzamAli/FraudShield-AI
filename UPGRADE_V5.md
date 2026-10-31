# FraudShield AI v5 — analytics and reliability upgrade

## Added
- Fraud Analytics screen with risk distribution, average score, volume, open cases, and daily transaction counts.
- `GET /api/analytics` aggregates synthetic records without exposing recipient identifiers.
- `GET /api/admin/transactions.csv` requires `X-Admin-Key`, with basic spreadsheet formula injection mitigation.
- Cached trusted local research model to avoid repeated joblib deserialization and version warnings on every prediction.
- Frontend WebSocket URL now follows `VITE_API_URL`.
- Pinned scikit-learn 1.8.0 to match the bundled research model.
- New tests for analytics, admin export permissions, and model caching.

## Run
Backend (from backend directory):
```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```
Frontend (from frontend directory):
```powershell
npm install
npm run dev
```
Tests (from backend directory):
```powershell
.\.venv\Scripts\python.exe -m pip install pytest httpx
.\.venv\Scripts\python.exe -m pytest tests -q
```

## Limitations
This remains an academic sandbox with rule-based simulated payment decisions and synthetic ML labels. No bank or UPI network is connected. Admin API key is a development-only control; use proper accounts, roles and secure session management before deployment.
