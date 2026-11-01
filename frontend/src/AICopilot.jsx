import React, {
  useCallback,
  useEffect,
  useState,
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
  FileDown,
} from "lucide-react";

import AIProviderMonitor from "./AIProviderMonitor";
import { downloadInvestigationPdf } from "./reportPdf";

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
    detail: "Invalid server response",
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
  const [provider, setProvider] = useState("auto");
  const [language, setLanguage] = useState("English");

  const [question, setQuestion] = useState(
    "Explain the strongest fraud risk indicators and recommend investigation steps."
  );

  const [transaction, setTransaction] = useState("");
  const [notes, setNotes] = useState("");
  const [image, setImage] = useState(null);

  const [result, setResult] = useState("");
  const [resultType, setResultType] = useState(null);
  const [resultMeta, setResultMeta] = useState(null);

  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const [status, setStatus] = useState(null);
  const [lastOutcome, setLastOutcome] = useState(null);

  const [history, setHistory] = useState([]);
  const [historyBusy, setHistoryBusy] = useState(false);
  const [historyError, setHistoryError] = useState("");

  const [monitorRefreshKey, setMonitorRefreshKey] =
    useState(0);

  const role = session?.user?.role;
  const permitted =
    role === "admin" || role === "analyst";

  const isAdmin = role === "admin";
  const token = session?.access_token;

  // ==========================================================
  // AI PROVIDER CONFIGURATION STATUS
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
          console.error("AI status failed", err);
        }
      }
    }

    fetchStatus();

    return () => controller.abort();
  }, [API, permitted, token]);

  // ==========================================================
  // LOAD SAVED AI INVESTIGATION HISTORY
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
  }, [API, token, permitted]);

  useEffect(() => {
    if (permitted && token) {
      loadHistory();
    } else {
      setHistory([]);
      setResult("");
      setResultMeta(null);
      setResultType(null);
      setLastOutcome(null);
    }
  }, [permitted, token, loadHistory]);

  // ==========================================================
  // READ REDACTED SCREENSHOT
  // ==========================================================

  function readImage(file) {
    setImage(null);
    setError("");

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
        "Choose a PNG, JPEG or WebP image up to 3 MB."
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
  // EXECUTE AI REQUEST
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
    setResultMeta(null);
    setResultType(null);
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

      const responseText =
        data.answer ||
        data.analysis ||
        data.report_markdown ||
        "No text returned";

      setResult(responseText);
      setResultType(tab);

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

      // Metadata for PDF reports
      setResultMeta({
        transactionId:
          data.transaction_id || transaction || null,

        provider: data.provider,
        model: data.model || "",

        historyId: data.history_id || null,
        createdAt: new Date().toISOString(),
      });

      await loadHistory();

    } catch (err) {
      setError(err.message);

    } finally {
      setBusy(false);
      setMonitorRefreshKey(value => value + 1);
    }
  }

  // ==========================================================
  // DOWNLOAD PLAIN TEXT
  // ==========================================================

  function downloadText() {
    if (!result) return;

    const content = [
      "FraudShield AI v11",
      "Academic Investigation Draft",
      "Human Review Required",
      "",
      `Provider: ${resultMeta?.provider ?? "unknown"}`,
      `Model: ${resultMeta?.model || "n/a"}`,
      "",
      result,
    ].join("\n");

    const blob = new Blob(
      [content],
      {
        type: "text/plain;charset=utf-8",
      }
    );

    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");

    anchor.href = url;
    anchor.download = `fraudshield-${Date.now()}.txt`;

    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();

    URL.revokeObjectURL(url);
  }

  // ==========================================================
  // PHASE 5: DOWNLOAD PROFESSIONAL PDF
  // ==========================================================

  function downloadCurrentPdf() {
    if (resultType !== "report" || !result) {
      setError(
        "Generate or open a case report first."
      );
      return;
    }

    try {
      setError("");

      downloadInvestigationPdf({
        reportText: result,
        transactionId: resultMeta?.transactionId,
        provider: resultMeta?.provider,
        model: resultMeta?.model,
        createdAt: resultMeta?.createdAt,
        historyId: resultMeta?.historyId,
      });

    } catch (err) {
      setError(
        err.message || "Unable to generate PDF."
      );
    }
  }

  function downloadSavedPdf(item) {
    if (item.operation !== "report") {
      return;
    }

    try {
      setError("");

      downloadInvestigationPdf({
        reportText: item.response_text,
        transactionId: item.transaction_id,
        provider: item.provider,
        model: item.model_name,
        createdAt: item.created_at,
        historyId: item.id,
      });

    } catch (err) {
      setError(
        err.message || "Unable to download saved PDF."
      );
    }
  }

  // ==========================================================
  // VIEW A SAVED RESPONSE
  // ==========================================================

  function viewSavedResponse(item) {
    const type =
      item.operation === "copilot"
        ? "ask"
        : item.operation === "screenshot"
        ? "screenshot"
        : "report";

    setTab(type);

    setResult(item.response_text);
    setResultType(type);

    setResultMeta({
      transactionId: item.transaction_id,
      provider: item.provider,
      model: item.model_name,
      createdAt: item.created_at,
      historyId: item.id,
    });

    setLastOutcome({
      provider: item.provider,
      model: item.model_name,
      requested: item.provider,
      fallbackUsed: false,
      fallbackReason: "",
      attempted: [],
    });

    setError("");
  }

  function changeTab(id) {
    setTab(id);
    setResult("");
    setResultType(null);
    setResultMeta(null);
    setLastOutcome(null);
    setError("");
  }

  // ==========================================================
  // MAIN USER INTERFACE
  // ==========================================================

  return (
    <section className="panel ai-workbench">

      <div className="panel-head">
        <div>
          <h3>
            <Bot size={21} />
            AI Fraud Investigation Copilot
          </h3>

          <p className="fine">
            Multi-provider AI · Automatic fallback ·
            Investigation history · PDF reports
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

          {/* AI TOOLS */}
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

          <div className="ai-columns">

            {/* LEFT: INPUT FORM */}
            <form
              className="payment-form"
              onSubmit={run}
            >

              {tab !== "screenshot" && (
                <label>
                  AI provider

                  <select
                    value={provider}
                    onChange={event =>
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
                    ].map(item => (
                      <option key={item} value={item}>
                        {item.toUpperCase()}
                        {status?.configured?.[item]
                          ? " — key configured"
                          : " — not configured"}
                      </option>
                    ))}
                  </select>

                  <small className="fine">
                    Text requests can use fallback
                    providers when supported.
                  </small>
                </label>
              )}

              {tab !== "screenshot" && (
                <label>
                  Simulated transaction

                  <select
                    value={transaction}
                    onChange={event =>
                      setTransaction(event.target.value)
                    }
                  >
                    <option value="">
                      {tab === "report"
                        ? "Choose transaction"
                        : "General guidance"}
                    </option>

                    {transactions.slice(0, 100).map(item => (
                      <option
                        key={item.id}
                        value={item.id}
                      >
                        {`#${item.id.slice(0, 8)} · ₹${Number(item.amount).toLocaleString("en-IN")} · ${item.risk}`}
                      </option>
                    ))}
                  </select>
                </label>
              )}

              {tab === "ask" && (
                <>
                  <label>
                    Response language

                    <select
                      value={language}
                      onChange={event =>
                        setLanguage(event.target.value)
                      }
                    >
                      {[
                        "English",
                        "Hindi",
                        "Telugu",
                      ].map(item => (
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
                      onChange={event =>
                        setQuestion(event.target.value)
                      }
                    />
                  </label>
                </>
              )}

              {tab === "screenshot" && (
                <>
                  <label>
                    Upload synthetic or redacted screenshot

                    <input
                      type="file"
                      accept="image/png,image/jpeg,image/webp"
                      onChange={event =>
                        readImage(event.target.files?.[0])
                      }
                    />
                  </label>

                  <p className="fine">
                    {image?.name ||
                      "PNG, JPEG or WebP · Maximum 3 MB"}
                  </p>

                  <p className="fine">
                    Image analysis uses Gemini only.
                  </p>
                </>
              )}

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
                    onChange={event =>
                      setNotes(event.target.value)
                    }
                    placeholder="Use synthetic or redacted data"
                  />
                </label>
              )}

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

            {/* RIGHT: AI RESPONSE */}
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

              {lastOutcome && (
                <div
                  style={{
                    marginBottom: 14,
                    padding: 12,
                    borderRadius: 10,
                    border: "1px solid #35517b",
                    background: "#14243d",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
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
                      Fallback activated:{" "}
                      {lastOutcome.fallbackReason}
                    </p>
                  )}

                  {lastOutcome.attempted.length > 1 && (
                    <p className="fine">
                      Sequence:{" "}
                      {lastOutcome.attempted.join(" → ")}
                    </p>
                  )}
                </div>
              )}

              {result ? (
                <>
                  <div className="ai-result">
                    {result}
                  </div>

                  <div
                    style={{
                      display: "flex",
                      flexWrap: "wrap",
                      gap: 10,
                      marginTop: 12,
                    }}
                  >
                    <button
                      type="button"
                      className="outline-btn"
                      onClick={downloadText}
                    >
                      <Download size={16} />
                      Download Text
                    </button>

                    {resultType === "report" && (
                      <button
                        type="button"
                        className="primary"
                        onClick={downloadCurrentPdf}
                      >
                        <FileDown size={16} />
                        Download PDF Report
                      </button>
                    )}
                  </div>
                </>
              ) : (
                <div className="empty">
                  <FileText size={40} />
                  <p>
                    AI output will appear here.
                    Every result requires human review.
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
                  Saved Copilot responses, screenshot
                  analyses and investigation reports.
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

                {history.map(item => (
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

                    <div
                      style={{
                        display: "flex",
                        flexWrap: "wrap",
                        gap: 10,
                      }}
                    >
                      <button
                        type="button"
                        className="outline-btn"
                        onClick={() =>
                          viewSavedResponse(item)
                        }
                      >
                        <Eye size={16} />
                        View Response
                      </button>

                      {item.operation === "report" && (
                        <button
                          type="button"
                          className="outline-btn"
                          onClick={() =>
                            downloadSavedPdf(item)
                          }
                        >
                          <FileDown size={16} />
                          Download PDF
                        </button>
                      )}
                    </div>
                  </article>
                ))}

              </div>
            )}
          </div>

          {/* ADMIN-ONLY PROVIDER MONITORING */}
          {isAdmin && (
            <AIProviderMonitor
              API={API}
              token={token}
              enabled={isAdmin}
              refreshKey={monitorRefreshKey}
            />
          )}

          {/* PRIVACY AND RESEARCH NOTICE */}
          <div className="research-warning">
            <ShieldAlert size={20} />

            <div>
              <b>Privacy and research limitations</b>

              <p>
                AI analysis uses external providers.
                Use synthetic or redacted data only.
                Responses are saved in investigation
                history. Provider monitoring records
                request outcomes and latency.

                PDF reports are generated locally
                in your browser from AI output.
                They are drafts, not certified fraud
                findings or final investigator decisions.
              </p>
            </div>
          </div>

        </>
      )}
    </section>
  );
}