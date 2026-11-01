
import React, {
  useCallback,
  useEffect,
  useState,
} from "react";

import {
  Activity,
  RefreshCw,
  ShieldCheck,
  AlertTriangle,
} from "lucide-react";

import "./AIProviderMonitor.css";


function formatTime(timestamp) {
  if (!timestamp) return "No activity";

  const date = new Date(timestamp);

  return Number.isNaN(date.getTime())
    ? "Unknown time"
    : date.toLocaleString();
}


function formatLatency(value) {
  return value == null
    ? "—"
    : `${Math.round(value)} ms`;
}


function HealthLabel({ health }) {
  const labels = {
    operational: "Operational",
    degraded: "Degraded",
    unavailable: "Unavailable",
    billing_issue: "Billing issue",
    access_issue: "Access issue",
    unknown: "No recent data",
    not_configured: "Not configured",
  };

  return (
    <span
      className={`monitor-health monitor-${health}`}
    >
      {labels[health] || "Unknown"}
    </span>
  );
}


export default function AIProviderMonitor({
  API,
  token,
  enabled = true,
  refreshKey = 0,
}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async (signal) => {
    if (!enabled || !token) return;

    setLoading(true);
    setError("");

    try {
      const response = await fetch(
        API + "/api/ai/monitor",
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
          signal,
        }
      );

      if (!response.ok) {
        throw new Error(
          `Monitoring request failed (${response.status})`
        );
      }

      const result = await response.json();

      if (!signal?.aborted) {
        setData(result);
      }

    } catch (err) {
      if (!signal?.aborted) {
        setError(err.message);
      }
    } finally {
      if (!signal?.aborted) {
        setLoading(false);
      }
    }

  }, [API, token, enabled]);


  useEffect(() => {
    if (!enabled || !token) {
      setData(null);
      return;
    }

    const controller = new AbortController();

    load(controller.signal);

    return () => controller.abort();
  }, [load, refreshKey, enabled, token]);


  if (!enabled || !token) return null;

  const providers = data?.providers || [];
  const recent = data?.recent_activity || [];

  return (
    <div className="monitor-panel">

      <div className="monitor-header">
        <div>
          <h3>
            <Activity size={21} />
            AI Provider Monitoring
          </h3>

          <p>
            Last 24 hours · Actual provider requests ·
            Administrator view
          </p>
        </div>

        <button
          type="button"
          className="outline-btn"
          disabled={loading}
          onClick={() => load()}
        >
          <RefreshCw size={16} />
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </div>


      {error && (
        <p className="error">
          <AlertTriangle size={15} />
          {" "}
          {error}
        </p>
      )}


      {data && (
        <>
          <div className="monitor-overview">

            <div className="monitor-overview-item">
              <span>Total requests</span>
              <strong>{data.monitored_attempts}</strong>
            </div>

            <div className="monitor-overview-item">
              <span>Successful requests</span>
              <strong>
                {providers.reduce(
                  (sum, item) => sum + item.successes,
                  0
                )}
              </strong>
            </div>

            <div className="monitor-overview-item">
              <span>Failed requests</span>
              <strong>
                {providers.reduce(
                  (sum, item) => sum + item.failures,
                  0
                )}
              </strong>
            </div>

            <div className="monitor-overview-item">
              <span>Successful fallback requests</span>
              <strong>
                {providers.reduce(
                  (sum, item) =>
                    sum + item.successful_fallbacks,
                  0
                )}
              </strong>
            </div>

          </div>


          <div className="monitor-provider-grid">
            {providers.map(item => (

              <article
                key={item.provider}
                className="monitor-provider-card"
              >

                <div className="monitor-provider-title">
                  <strong>
                    {item.provider.toUpperCase()}
                  </strong>

                  <HealthLabel health={item.health} />
                </div>

                <div className="monitor-stat-line">
                  <span>Requests</span>
                  <b>{item.requests}</b>
                </div>

                <div className="monitor-stat-line">
                  <span>Successful</span>
                  <b>{item.successes}</b>
                </div>

                <div className="monitor-stat-line">
                  <span>Failed</span>
                  <b>{item.failures}</b>
                </div>

                <div className="monitor-stat-line">
                  <span>Success rate</span>
                  <b>
                    {item.success_rate == null
                      ? "—"
                      : `${item.success_rate}%`}
                  </b>
                </div>

                <div className="monitor-stat-line">
                  <span>Average latency</span>
                  <b>
                    {formatLatency(
                      item.average_latency_ms
                    )}
                  </b>
                </div>

                <div className="monitor-stat-line">
                  <span>Fallback successes</span>
                  <b>{item.successful_fallbacks}</b>
                </div>

                <div className="monitor-stat-line">
                  <span>Last request</span>
                  <small>
                    {formatTime(item.last_request_at)}
                  </small>
                </div>

                {item.last_error_reason && (
                  <p className="monitor-last-error">
                    Last failure: {item.last_error_reason}
                  </p>
                )}

              </article>

            ))}
          </div>


          <div className="monitor-activity">
            <h4>
              <ShieldCheck size={18} />
              Recent Provider Activity
            </h4>

            {recent.length === 0 ? (
              <p className="fine">
                No AI provider attempts recorded yet.
              </p>
            ) : (
              <div className="monitor-table-wrap">
                <table className="monitor-table">
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Provider</th>
                      <th>Result</th>
                      <th>Latency</th>
                      <th>Type</th>
                    </tr>
                  </thead>

                  <tbody>
                    {recent.map(item => (
                      <tr key={item.id}>
                        <td>
                          {formatTime(item.created_at)}
                        </td>

                        <td>
                          {item.provider.toUpperCase()}
                        </td>

                        <td>
                          {item.success
                            ? "Success"
                            : item.error_reason ||
                              `HTTP ${item.status_code || "error"}`}
                        </td>

                        <td>
                          {formatLatency(item.latency_ms)}
                        </td>

                        <td>
                          {item.fallback_step
                            ? "Fallback"
                            : "Primary / direct"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>


          <p className="fine monitor-disclaimer">
            {data.note}
          </p>
        </>
      )}

    </div>
  );
}
