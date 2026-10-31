# FraudShield AI v4 — upgrade notes

## New features
- Added a **separate** simulator-aligned Random Forest research model and reproducible training script (`ml/train_sandbox.py`). It uses six inputs that match the live payment form.
- `/api/ml/sandbox-predict` returns an **experimental** score from synthetic labels, alongside the existing transparent rule-based decision.
- `/api/ml/sandbox-metrics` exposes the research model's held-out evaluation results.
- The simulator displays rule-based risk and experimental ML results separately.
- Investigation page includes admin-key-protected review/close controls. The admin key is entered into the UI and held in React state only; do not use it in a production deployment.
- API URL can be configured using `frontend/.env` with `VITE_API_URL`.

## Limitations
- The original synthetic dataset remains research-only; its perfect performance is not real-world fraud accuracy.
- The new model also learns **synthetic labels**, not verified fraud outcomes. It must not be used to block payments or claim bank-grade accuracy.
- The rule-based engine remains the source of simulated payment decisions.
- This version does not implement account login, JWT, production security, GAN live inference, SHAP, or production-grade audit logging.
- The public sandbox WebSocket exposes simulated transactions. Do not use real user financial data.

## Run (Windows PowerShell)
From `backend`:
```
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```
From `frontend` (another terminal):
```
npm install
npm run dev
```
Train/retrain the research model from the project root:
```
.\backend\.venv\Scripts\python.exe ml\train_sandbox.py
```

## Administrator review
Set `ADMIN_API_KEY` in the backend environment **before** starting FastAPI. Example in PowerShell (development only):
```
$env:ADMIN_API_KEY="replace-with-a-long-random-local-test-secret"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```
Enter the same key on the Investigations page. This is a prototype control, not production authentication.

## Validation
From `backend`, install `pytest` and `httpx` if necessary, then run `python -m pytest tests -q`.
