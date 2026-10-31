# FraudShield AI v10 — Multi-AI Fraud Copilot

This release is an upgrade of v9. Keep v9 as a backup. **Not a real payment platform. All test data must be synthetic or redacted.**

## Included
- **Fraud Copilot:** analyst/admin-only text questions in English, Hindi, Telugu using OpenAI, Gemini, or Groq.
- **Gemini screenshot inspection:** redacted PNG/JPEG/WebP images up to 3 MB.
- **AI case report draft:** structured text report tied to an existing sandbox transaction, with manual download.
- **Provider configuration status** for authorized analysts, without revealing keys.
- Uses existing Firebase ID token verification, backend user roles, case records and dashboard.
- Existing rules-based fraud verdicts remain unchanged; AI is advisory only.
- The backend deliberately omits raw UPI identifiers from context it automatically sends to AI providers.

## Configuration
1. Extract this ZIP and open `FraudShield_AI_v10` in VS Code.
2. Inside `backend`, create `.env` from `.env.example`, then copy the **working** v9 Firebase project ID, admin credential file path and `AUTH_MODE=firebase` configuration (never copy JSON private keys into this project). Keep `GOOGLE_APPLICATION_CREDENTIALS` pointing to a private file outside your repository.
3. Inside `frontend`, create `.env.local` from `.env.example` and copy the Firebase web config from v9.
4. Add your provider keys **only to backend/.env**:

```env
OPENAI_API_KEY=your_key_here
GEMINI_API_KEY=your_key_here
GROQ_API_KEY=your_key_here
OPENAI_MODEL=gpt-4.1-mini
GEMINI_MODEL=gemini-2.5-flash
GROQ_MODEL=llama-3.3-70b-versatile
```

You only need one configured text provider for Copilot and report generation. Gemini is required for screenshot analysis. Provider availability, model entitlements and billing vary. Change the model setting if your API account does not support the default.

## Windows setup
Backend (`backend` directory):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Frontend (`frontend` directory):

```powershell
npm install
npm run build
npm run dev
```

**Use `npm install` first**, not `npm ci`: the inherited v9 package lock may be out of sync with `package.json`. Keep the generated lockfile once updated.

## Demo
1. Log in as your Firebase-verified `admin` or `analyst` account.
2. Run a few **synthetic** payments in the UPI Sandbox.
3. Open the new **AI Fraud Copilot** sidebar page.
4. Choose OpenAI/Gemini/Groq; ask a question about a selected synthetic transaction.
5. Switch to **Gemini Image Analysis** and upload a **redacted** mock fraud screenshot.
6. Switch to **Case Report**, select a transaction, add simulated analyst notes and generate/download the draft.
7. Confirm that the risk score and review status do not change after an AI request.

## API routes (Firebase Authorization: Bearer ID token required)
- `GET /api/ai/status` — provider key presence, analyst/admin.
- `POST /api/ai/ask` — question, optional transaction ID, provider, language.
- `POST /api/ai/screenshot` — base64 image, media type, optional description; Gemini only.
- `POST /api/ai/report` — selected transaction ID, analyst notes, provider.

## Tests / known limitations
- All 23 backend tests passed in the build environment (18 inherited + 5 new).
- Source compilation passed. Browser UI, live provider APIs and Docker were **not** exercised in this environment. Run `npm run build` and local walkthrough yourself.
- Model performance remains synthetic; language-model text is not ground truth.
- A generated report is a draft, not recorded automatically as a finalized investigation or audit decision.
- **Existing v9 public endpoints remain public**, including transaction listings and WebSocket. This is an academic sandbox, not a secure production deployment. Do not add real users' financial information. Protect those endpoints and add server-side rate limits, provider budgets and audit logging before production use.
- An image gets sent to Gemini; only upload test/redacted content with consent.
- No automatic provider fallback is enabled (avoids sharing information with an unintended service).
- AI provider request timeout is approximately 28s, and HTTP provider errors are sanitized to avoid echoing private request data.
