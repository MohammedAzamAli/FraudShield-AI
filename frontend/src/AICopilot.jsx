
import React, {
  useState,
  useEffect,
  useCallback,
} from "react";

import {
  Bot,
  FileText,
  ShieldAlert,
  Send,
  Download,
  RefreshCw,
  History,
  Eye,
  CheckCircle2,
  AlertTriangle,
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
// MAIN AI COPILOT COMPONENT
// ============================================================

export default function AICopilot({
  API,
  session,
  transactions = [],
}) {
  const [tab, setTab] = useState("ask");
  const [provider, setProvider] = useState("auto");
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
  const [lastOutcome, setLastOutcome] = useState(null);

  const [history, setHistory] = useState([]);
  const [historyBusy, setHistoryBusy] = useState(false);
  const [historyError, setHistoryError] = useState("");

  const role = session?.user?.role;
  const permitted =
    role === "admin" || role === "analyst";
  const token = session?.access_token;


  // ==========================================================
  // PROVIDER STATUS
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

        if (!response.ok) return;

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

  }, [API, permitted, token]);


  // ==========================================================
  // LOAD INVESTIGATION HISTORY
  // ==========================================================

  const loadHistory = useCallback(async () => {
    if (!permitted || !token) return;

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
          `History request failed (${response.status})`
        );
      }

      const data = await response.json();

      setHistory(
        Array.isArray(data) ? data : []
      );

    } catch (err) {
      setHistoryError(err.message);

    } finally {
      setHistoryBusy(false);
    }

  }, [API, permitted, token]);


  // ==========================================================
  // LOAD HISTORY ON AUTHENTICATION
  // ==========================================================

  useEffect(() => {
    if (permitted && token) {
      loadHistory();
    } else {
      setHistory([]);
      setResult("");
      setLastOutcome(null);
    }
  }, [permitted, token, loadHistory]);


  // ==========================================================
  // IMAGE FILE READER
  // ==========================================================

  function readImage(file) {
    setError("");
    setImage(null);

    if (!file) return;

    const allowed = [
      "image/png",
      "image/jpeg",
      "image/webp",
    ];

    if (
      !allowed.includes(file.type) ||
      file.size > 3 * 1024 * 1024
    ) {
      setError(
        "Choose a PNG, JPEG, or WebP image up to 3 MB."
      );
      return;
    }

    const reader = new FileReader();

    reader.onload = () => {
      setImage({
        name: file.name,
        mime_type: file.type,
        image_base64: String(
          reader.result
        ).split(",")[1],
      });
    };

    reader.onerror = () => {
      setError("Unable to read screenshot.");
    };

    reader.readAsDataURL(file);
  }


  // ==========================================================
  // SUBMIT AI REQUEST
  // ==========================================================

  async function run(event) {
    event.preventDefault();

    if (!permitted || !token) {
      setError(
        "Analyst or administrator login required."
      );
      return;
    }

    setError("");
    setResult("");
    setLastOutcome(null);
    setBusy(true);

    try {
      let route;
      let payload;

      if (tab === "ask") {
        route = "/api/ai/ask";

        payload = {
          question,
          provider,
          language,
          transaction_id: transaction || null,
        };

      } else if (tab === "screenshot") {
        if (!image) {
          throw new Error(
            "Choose a screenshot first."
          );
        }

        route = "/api/ai/screenshot";

        payload = {
          mime_type: image.mime_type,
          image_base64: image.image_base64,
          description: notes,
        };

      } else {
        if (!transaction) {
          throw new Error(
            "Choose a transaction first."
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
        payload,
      );

      setResult(
        data.answer ||
        data.analysis ||
        data.report_markdown ||
        "No text returned."
      );

      setLastOutcome({
        provider: data.provider,
        model: data.model || "",
        requested: data.requested_provider || provider,
        fallbackUsed: Boolean(
          data.fallback_used
        ),
        fallbackReason: data.fallback_reason || "",
        attempted: data.attempted_providers || [],
      });

      await loadHistory();

    } catch (err) {
      setError(err.message);

    } finally {
      setBusy(false);
    }
  }


  // ==========================================================
  // DOWNLOAD AI RESULT
  // ==========================================================

  function save() {
    if (!result) return;

    const content = [
      "FraudShield AI v11",
      "Synthetic Investigation Draft",
      "Human review required",
      "",
      `Provider: ${lastOutcome?.provider || "Unknown"}`,
      `Model: ${lastOutcome?.model || "Unknown"}`,
      "",
      result,
    ].join("\n");

    const blob = new Blob(
      [content],
      {
        type: "text/plain;charset=utf-8",
      },
    );

    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");

    anchor.href = url;
    anchor.download = `fraudshield-${tab}-draft.txt`;

    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();

    URL.revokeObjectURL(url);
  }


  // ==========================================================
  // SWITCH TABS
  // ==========================================================

  function changeTab(id) {
    setTab(id);
    setResult("");
    setError("");
    setLastOutcome(null);
  }


  // ==========================================================
  // RENDER
  // ==========================================================

  return (
    <section className="panel ai-workbench">

      {/* HEADING */}
      <div className="panel-head">
        <div>
          <h3>
            <Bot size={21} />
            AI Fraud Investigation Copilot
          </h3>

          <p className="fine">
            Multi-provider AI · Automatic fallback ·
            Persistent investigation history
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
              to access the AI workbench.
            </p>
          </div>
        </div>

      ) : (

        <>
          {/* MODE TABS */}
          <div className="filter-pills">
            {[
              ["ask", "Fraud Copilot"],
              ["screenshot", "Gemini Image Analysis"],
              ["report", "Case Report"],
            ].map(([id, label]) => (

              <button
                type="button"
                key={id}
                className={tab === id ? "selected" : ""}
                onClick={() => changeTab(id)}
              >
                {label}
              </button>

            ))}
          </div>


          {/* MAIN WORKBENCH */}
          <div className="ai-columns">

            <form
              className="payment-form"
              onSubmit={run}
            >

              {/* PROVIDER DROPDOWN */}
              {tab !== "screenshot" && (
                <label>
                  AI provider

                  <select
                    value={provider}
                    onChange={(event) =>
                      setProvider(event.target.value)
                    }
                  >
                    <option value="auto">
                      AUTOMATIC (Gemini → Groq)
                    </option>

                    {[
                      "gemini",
                      "groq",
                      "openai",
                    ].map((item) => (
                      <option
                        key={item}
                        value={item}
                      >
                        {item.toUpperCase()}
                        {status?.configured?.[item]
                          ? " — key configured"
                          : " — not configured"}
                      </option>
                    ))}
                  </select>

                  <small className="fine">
                    If the selected text provider has a
                    temporary failure, FraudShield AI can
                    try an alternative provider.
                  </small>
                </label>
              )}


              {/* TRANSACTION */}
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
                        ? "Choose transaction"
                        : "General guidance"}
                    </option>

                    {transactions.slice(0, 100).map((item) => (
                      <option
                        key={item.id}
                        value={item.id}
                      >
                        #{item.id.slice(0, 8)}
                        {" · ₹"}
                        {Number(item.amount).toLocaleString("en-IN")}
                        {" · "}
                        {item.risk}
                      </option>
                    ))}
                  </select>
                </label>
              )}


              {/* QUESTION */}
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


              {/* SCREENSHOT */}
              {tab === "screenshot" && (
                <>
                  <label>
                    Upload synthetic or redacted screenshot

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
                      "PNG, JPEG, WebP · Maximum 3 MB"}
                  </p>

                  <p className="fine">
                    Screenshot analysis uses Gemini only.
                    No text-only fallback is attempted.
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
                    placeholder="Use only synthetic or redacted data"
                  />
                </label>
              )}


              {/* SUBMIT */}
              <button
                type="submit"
                className="primary"
                disabled={busy}
              >
                <Send size={16} />

                {busy
                  ? "Processing AI request..."
                  : tab === "ask"
                    ? "Ask Copilot"
                    : tab === "screenshot"
                      ? "Analyze Screenshot"
                      : "Generate Report"}
              </button>

            </form>


            {/* AI RESULT PANEL */}
            <div className="ai-response">

              <h4>
                {tab === "ask"
                  ? "AI Assessment"
                  : tab === "screenshot"
                    ? "Screenshot Observations"
                    : "Investigation Draft"}
              </h4>

              {error && (
                <p className="error">
                  <AlertTriangle size={15} />
                  {" "}
                  {error}
                </p>
              )}


              {/* PROVIDER ACTUALLY USED */}
              {lastOutcome && (
                <div
                  style={{
                    marginBottom: 14,
                    padding: 12,
                    borderRadius: 10,
                    border: "1px solid #35517b",
                    background: "#14243d",
                    color: "#dbe8fb",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      flexWrap: "wrap",
                    }}
                  >
                    {lastOutcome.fallbackUsed
                      ? <RefreshCw size={16} />
                      : <CheckCircle2 size={16} />
                    }

                    <strong>
                      Answered by{" "}
                      {lastOutcome.provider?.toUpperCase()}
                    </strong>
                  </div>

                  {lastOutcome.model && (
                    <p className="fine">
                      Model: {lastOutcome.model}
                    </p>
                  )}

                  {lastOutcome.fallbackUsed && (
                    <p className="fine">
                      Automatic fallback activated.
                      Previous provider issue:{" "}
                      {lastOutcome.fallbackReason}.
                    </p>
                  )}

                  {lastOutcome.attempted.length > 1 && (
                    <p className="fine">
                      Provider sequence:{" "}
                      {lastOutcome.attempted.join(" → ")}
                    </p>
                  )}
                </div>
              )}


              {/* OUTPUT */}
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
                    Responses are advisory and require
                    independent verification.
                  </p>
                </div>
              )}
            </div>

          </div>


          {/* PERSISTENT INVESTIGATION HISTORY */}
          <div className="ai-history-panel">

            <div className="ai-history-heading">
              <div>
                <h3>
                  <History size={21} />
                  AI Investigation History
                </h3>

                <p className="fine">
                  Previous Copilot responses, screenshot
                  analyses and investigation drafts.
                </p>
              </div>

              <button
                type="button"
                className="outline-btn"
                disabled={historyBusy}
                onClick={loadHistory}
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
                      onClick={() => {
                        setResult(item.response_text);
                        setLastOutcome({
                          provider: item.provider,
                          model: item.model_name,
                          requested: item.provider,
                          fallbackUsed: false,
                          fallbackReason: "",
                          attempted: [],
                        });
                      }}
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
              <b>Privacy and AI limitations</b>

              <p>
                Text investigations may be sent to a
                fallback external AI provider if the
                primary provider is unavailable.
                Use synthetic or redacted data only.
                Generated outputs are stored in the
                investigation history database.

                Screenshot analysis uses Gemini only.
                AI output does not automatically change
                transaction risk classifications or
                close investigation cases.
              </p>
            </div>
          </div>

        </>
      )}

    </section>
  );
}
