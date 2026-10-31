# FraudShield AI v6 — Visual Command Center

## New in v6
- Redesigned dashboard header and active navigation styling
- Backend-driven 7-active-day stacked risk trend and donut risk distribution
- High-risk recent transactions card and investigation shortcut
- Risk-level transaction filters
- Reports page with sandbox KPI cards and admin-protected CSV export
- Live notification indicator for cases requiring review
- Responsive styles with the original v5 API, simulator, QR inspection, ML research, analytics and case review preserved

## Windows setup
1. Extract ZIP, open `FraudShield_AI_v6` in VS Code.
2. Backend terminal: `cd backend`; `py -3.12 -m venv .venv`; `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`; `.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload`.
3. Frontend terminal: `cd frontend`; `npm install`; `npm run dev`.
4. Open the address shown by Vite, typically http://127.0.0.1:5173.

## Admin export
Set ADMIN_API_KEY in the backend process environment, restart backend, enter matching key on Investigations screen, and use Reports -> Download transaction CSV. Never commit or expose the key.

## Scope
This is a sandbox visualization and workflow upgrade, not a new validated real-world fraud detector. The payment decision remains rule-based; experimental ML predictions are research-only. Real login/roles, SHAP, real-world model evaluation and production deployment remain future milestones.
