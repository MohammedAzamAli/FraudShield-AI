
import React, {
  useState,
  useEffect,
  useCallback,
} from "react";

import {
  Bot,
  ImageUp,
  FileText,
  ShieldAlert,
  Send,
  Download,
  RefreshCw,
  History,
  Eye,
} from "lucide-react";

import "./AIHistory.css";


// ============================================================
// API REQUEST HELPER
// ============================================================

async function request(API, route, token, payload) {
  const response = await fetch(API + route, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });

  const data = await response.json().catch(() => ({
    detail: "Invalid response from server",
  }));

  if (!response.ok) {
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : `Request failed (${response.status})`
    );
  }

  return data;
}


// ============================================================
// MAIN COMPONENT
// ============================================================

export default function AICopilot({
  API,
  session,
  transactions = [],
}) {
  const [tab, setTab] = useState("ask");
  const [provider, setProvider] = useState("gemini");
  const [language, setLanguage] = useState("English");

  const [question, setQuestion] = useState(
    "Explain the strongest risk indicators and what an investigator should check next."
  );

  const [transaction, setTransaction] = useState("");
  const [notes, setNotes] = useState("");
  const [image, setImage] = useState(null);

  const [result, setResult] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState(null);

  // v11 history states
  const [history, setHistory] = useState([]);
  const [historyBusy, setHistoryBusy] = useState(false);
  const [historyError, setHistoryError] = useState("");

  const role = session?.user?.role;

  const permitted =
    role === "admin" || role === "analyst";

  const token = session?.access_token;


  // ==========================================================
  // FETCH AI PROVIDER STATUS
  // ==========================================================

  useEffect(() => {
    if (!permitted || !token) {
      setStatus(null);
      return;
    }

    const controller = new AbortController();

    async function fetchStatus() {
      try {
        const response = await fetch(
          API + "/api/ai/status",
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
            signal: controller.signal,
          }
        );

        if (!response.ok) {
          throw new Error(
            `Provider status failed: ${response.status}`
          );
        }

        const data = await response.json();

        if (!controller.signal.aborted) {
          setStatus(data);
        }

      } catch (err) {
        if (!controller.signal.aborted) {
          console.error("AI status error:", err);
        }
      }
    }

    fetchStatus();

    return () => controller.abort();

  }, [API, token, permitted]);


  // ==========================================================
  // v11: LOAD AI INVESTIGATION HISTORY
  // ==========================================================

  const loadHistory = useCallback(async () => {
    if (!permitted || !token) {
      return;
    }

    setHistoryBusy(true);
    setHistoryError("");

    try {
      const response = await fetch(
        API + "/api/ai/history?limit=30",
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) {
        throw new Error(
          `Unable to load history (${response.status})`
        );
      }

      const data = await response.json();
      setHistory(Array.isArray(data) ? data : []);

    } catch (err) {
      setHistoryError(err.message);
      console.error("History error:", err);

    } finally {
      setHistoryBusy(false);
    }

  }, [API, token, permitted]);


  // ==========================================================
  // AUTO-LOAD HISTORY AFTER LOGIN
  // ==========================================================

  useEffect(() => {
    if (permitted && token) {
      loadHistory();
    } else {
      setHistory([]);
      setHistoryError("");
      setResult("");
    }
  }, [permitted, token, loadHistory]);


  // ==========================================================
  // SCREENSHOT FILE READER
  // ==========================================================

  async function readImage(file) {
    if (!file) return;

    setError("");
    setImage(null);

    const allowedTypes = [
      "image/png",
      "image/jpeg",
      "image/webp",
    ];

    if (
      !allowedTypes.includes(file.type) ||
      file.size > 3 * 1024 * 1024
    ) {
      setError(
        "Select a PNG, JPEG or WebP image up to 3 MB."
      );
      return;
    }

    const reader = new FileReader();

    reader.onload = () => {
      setImage({
        mime_type: file.type,
        image_base64: String(reader.result).split(",")[1],
        name: file.name,
      });
    };

    reader.onerror = () => {
      setError("Unable to read the selected image.");
    };

    reader.readAsDataURL(file);
  }


  // ==========================================================
  // RUN AI REQUEST
  // ==========================================================

  async function run(event) {
    event.preventDefault();

    if (!permitted || !token) {
      setError("Analyst or administrator login required.");
      return;
    }

    setError("");
    setResult("");
    setBusy(true);

    try {
      let route;
      let payload;

      // FRAUD COPILOT
      if (tab === "ask") {
        route = "/api/ai/ask";

        payload = {
          question,
          provider,
          language,
          transaction_id: transaction || null,
        };
      }

      // SCREENSHOT ANALYSIS
      else if (tab === "screenshot") {
        if (!image) {
          throw new Error("Choose an image first.");
        }

        route = "/api/ai/screenshot";

        payload = {
          mime_type: image.mime_type,
          image_base64: image.image_base64,
          description: notes,
        };
      }

      // INVESTIGATION REPORT
      else {
        if (!transaction) {
          throw new Error(
            "Select a simulated transaction first."
          );
        }

        route = "/api/ai/report";

        payload = {
          transaction_id: transaction,
          analyst_notes: notes,
          provider,
        };
      }

      const data = await request(
        API,
        route,
        token,
        payload
      );

      setResult(
        data.answer ||
        data.analysis ||
        data.report_markdown ||
        "No text returned"
      );

      // v11: Reload saved AI investigation history
      await loadHistory();

    } catch (err) {
      setError(err.message);

    } finally {
      setBusy(false);
    }
  }


  // ==========================================================
  // DOWNLOAD RESULT
  // ==========================================================

  function save() {
    if (!result) return;

    const content =
      "FraudShield AI v11 — Investigation Draft\n" +
      "SYNTHETIC SANDBOX ONLY\n" +
      "HUMAN REVIEW REQUIRED\n\n" +
      result;

    const blob = new Blob(
      [content],
      { type: "text/plain;charset=utf-8" }
    );

    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");

    anchor.href = url;
    anchor.download = `fraudshield-${tab}-draft.txt`;

    anchor.click();

    URL.revokeObjectURL(url);
  }


  // ==========================================================
  // CHANGE TAB
  // ==========================================================

  function changeTab(id) {
    setTab(id);
    setResult("");
    setError("");

    if (id === "screenshot") {
      setProvider("gemini");
    }
  }


  // ==========================================================
  // FRONTEND
  // ==========================================================

  return (
    <section className="panel ai-workbench">

      {/* HEADER */}
      <div className="panel-head">
        <div>
          <h3>
            <Bot size={21} />
            AI Fraud Investigation Copilot
          </h3>

          <p className="fine">
            Analyst-only assistant · Synthetic or redacted
            data only · Persistent investigation history
          </p>
        </div>

        <span className="tag">
          ADVISORY — HUMAN REVIEW
        </span>
      </div>


      {!permitted ? (

        <div className="research-warning">
          <ShieldAlert size={20} />

          <div>
            <b>Authentication required</b>

            <p>
              Sign in as an analyst or administrator
              to access the AI investigation tools.
            </p>
          </div>
        </div>

      ) : (

        <>
          {/* TABS */}
          <div className="filter-pills">
            {[
              ["ask", "Fraud Copilot"],
              ["screenshot", "Gemini Image Analysis"],
              ["report", "Case Report"],
            ].map(([id, label]) => (

              <button
                key={id}
                type="button"
                className={tab === id ? "selected" : ""}
                onClick={() => changeTab(id)}
              >
                {label}
              </button>

            ))}
          </div>


          {/* AI WORKBENCH */}
          <div className="ai-columns">

            <form
              className="payment-form"
              onSubmit={run}
            >

              {/* PROVIDER */}
              {tab !== "screenshot" && (
                <label>
                  AI provider

                  <select
                    value={provider}
                    onChange={(event) =>
                      setProvider(event.target.value)
                    }
                  >
                    {[
                      "openai",
                      "gemini",
                      "groq",
                    ].map((item) => (

                      <option
                        key={item}
                        value={item}
                      >
                        {item.toUpperCase()}
                        {status?.configured?.[item]
                          ? " ✓ key configured"
                          : ""}
                      </option>

                    ))}
                  </select>
                </label>
              )}


              {/* TRANSACTION SELECTION */}
              {tab !== "screenshot" && (
                <label>
                  Simulated transaction

                  <select
                    value={transaction}
                    onChange={(event) =>
                      setTransaction(event.target.value)
                    }
                  >
                    <option value="">
                      {tab === "report"
                        ? "Choose a transaction"
                        : "General guidance (no transaction)"}
                    </option>

                    {transactions.slice(0, 100).map((item) => (

                      <option
                        key={item.id}
                        value={item.id}
                      >
                        #{item.id.slice(0, 8)}
                        {" · ₹"}
                        {item.amount.toLocaleString("en-IN")}
                        {" · "}
                        {item.risk}
                      </option>

                    ))}
                  </select>
                </label>
              )}


              {/* ASK COPILOT */}
              {tab === "ask" && (
                <>
                  <label>
                    Response language

                    <select
                      value={language}
                      onChange={(event) =>
                        setLanguage(event.target.value)
                      }
                    >
                      {[
                        "English",
                        "Hindi",
                        "Telugu",
                      ].map((item) => (
                        <option key={item}>
                          {item}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label>
                    Investigation question

                    <textarea
                      rows={5}
                      required
                      maxLength={1200}
                      value={question}
                      onChange={(event) =>
                        setQuestion(event.target.value)
                      }
                    />
                  </label>
                </>
              )}


              {/* IMAGE ANALYSIS */}
              {tab === "screenshot" && (
                <>
                  <label>
                    Upload redacted screenshot

                    <input
                      type="file"
                      accept="image/png,image/jpeg,image/webp"
                      onChange={(event) =>
                        readImage(event.target.files?.[0])
                      }
                    />
                  </label>

                  <p className="fine">
                    {image?.name ||
                      "PNG, JPEG or WebP up to 3 MB. Remove personal information before uploading."}
                  </p>
                </>
              )}


              {/* NOTES */}
              {tab !== "ask" && (
                <label>
                  {tab === "report"
                    ? "Investigation notes"
                    : "Optional screenshot context"}

                  <textarea
                    rows={4}
                    maxLength={
                      tab === "report" ? 1500 : 450
                    }
                    value={notes}
                    onChange={(event) =>
                      setNotes(event.target.value)
                    }
                    placeholder="Synthetic or redacted information only"
                  />
                </label>
              )}


              {/* SUBMIT BUTTON */}
              <button
                type="submit"
                className="primary"
                disabled={busy}
              >
                <Send size={16} />

                {busy
                  ? "Contacting provider..."
                  : tab === "ask"
                    ? "Ask Copilot"
                    : tab === "screenshot"
                      ? "Analyze screenshot"
                      : "Draft investigation report"}
              </button>

            </form>


            {/* AI RESPONSE */}
            <div className="ai-response">

              <h4>
                {tab === "ask"
                  ? "AI Assessment"
                  : tab === "screenshot"
                    ? "Screenshot Observations"
                    : "Draft Report"}
              </h4>

              {error && (
                <p className="error">
                  {error}
                </p>
              )}

              {result ? (

                <>
                  <div className="ai-result">
                    {result}
                  </div>

                  <button
                    type="button"
                    className="outline-btn"
                    onClick={save}
                  >
                    <Download size={16} />
                    Download Draft
                  </button>
                </>

              ) : (

                <div className="empty">
                  <FileText size={40} />

                  <p>
                    AI output will appear here.
                    Results are advisory and may
                    contain errors.
                  </p>
                </div>

              )}
            </div>
          </div>


          {/* v11: PERSISTENT INVESTIGATION HISTORY */}
          <div className="ai-history-panel">

            <div className="ai-history-heading">

              <div>
                <h3>
                  <History size={21} />
                  AI Investigation History
                </h3>

                <p className="fine">
                  Saved AI explanations, screenshot
                  analyses and investigation reports.
                </p>
              </div>

              <button
                type="button"
                className="outline-btn"
                onClick={loadHistory}
                disabled={historyBusy}
              >
                <RefreshCw size={16} />
                {historyBusy
                  ? "Loading..."
                  : "Refresh History"}
              </button>
            </div>


            {historyError && (
              <p className="error">
                {historyError}
              </p>
            )}


            {history.length === 0 ? (

              <p className="fine">
                No saved AI investigations found.
              </p>

            ) : (

              <div className="ai-history-list">

                {history.map((item) => (

                  <article
                    key={item.id}
                    className="ai-history-item"
                  >

                    <div className="ai-history-meta">
                      <strong>
                        {item.operation.toUpperCase()}
                      </strong>

                      <span>{item.provider}</span>
                      <span>{item.model_name}</span>

                      <span>
                        {item.created_at
                          ? new Date(
                              item.created_at
                            ).toLocaleString()
                          : "Unknown date"}
                      </span>
                    </div>


                    {item.transaction_id && (
                      <p className="fine">
                        Transaction: #
                        {item.transaction_id.slice(0, 8)}
                      </p>
                    )}


                    <p className="ai-history-preview">
                      {item.response_text.slice(0, 240)}

                      {item.response_text.length > 240
                        ? "..."
                        : ""}
                    </p>


                    <button
                      type="button"
                      className="outline-btn"
                      onClick={() =>
                        setResult(item.response_text)
                      }
                    >
                      <Eye size={16} />
                      View Saved Response
                    </button>

                  </article>

                ))}

              </div>
            )}

          </div>


          {/* PRIVACY WARNING */}
          <div className="research-warning">
            <ShieldAlert size={20} />

            <div>
              <b>Privacy and research limitations</b>

              <p>
                AI requests are sent to external providers.
                Use synthetic or redacted information only.
                Generated responses are saved in the local
                database for investigation history.

                Uploaded screenshot bytes are not stored
                in the history table.

                AI results never automatically change fraud
                classifications or close investigation cases.
              </p>
            </div>
          </div>

        </>

      )}

    </section>
  );
}
