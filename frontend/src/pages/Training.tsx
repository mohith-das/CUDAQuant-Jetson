import { Fragment, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { apiFetch } from "../api";
import { AuthErrorBox, isAuthError } from "../AuthErrorBox";

type Universe = { id: string; name: string; symbols: string[] };
type Run = {
  id?: string;
  status?: string;
  model_id?: string | null;
  metrics?: Record<string, unknown> | null;
  error?: string | null;
  symbols?: string[] | null;
  model_family?: string | null;
  features?: string[] | null;
  horizon?: number | null;
};

const CUSTOM = "__custom__";
const FEATURES = ["returns", "log_returns"];

const apiError = (err: unknown): string => {
  const msg = (err as Error).message || String(err);
  const m = msg.match(/^API (\d+): (.*)$/s);
  if (m) {
    try {
      const body = JSON.parse(m[2]);
      if (typeof body?.detail === "string") return `${m[1]}: ${body.detail}`;
    } catch {
      /* non-JSON error body */
    }
  }
  return msg;
};

const statusPill = (status: string) => {
  const cls =
    status === "completed" ? "pill-positive"
    : status === "failed" ? "pill-negative"
    : "pill-accent";
  return <span className={`pill ${cls}`}>{status}</span>;
};

const fmtMetrics = (m: unknown) => {
  if (!m || (typeof m === "object" && Object.keys(m as object).length === 0)) return "—";
  return JSON.stringify(m).slice(0, 60);
};

export default function Training() {
  const queryClient = useQueryClient();
  const [universeId, setUniverseId] = useState("");
  const [customSymbols, setCustomSymbols] = useState("");
  const [modelFamily, setModelFamily] = useState("logistic_regression");
  const [features, setFeatures] = useState<Record<string, boolean>>({ returns: true, log_returns: false });
  const [horizon, setHorizon] = useState("5");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<Run | null>(null);
  const [runError, setRunError] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const universes = useQuery({
    queryKey: ["universes"],
    queryFn: () => apiFetch<Universe[]>("/api/universe/"),
  });
  const runs = useQuery({
    queryKey: ["training"],
    queryFn: () => apiFetch<Run[]>("/api/training/?limit=50"),
    refetchInterval: 10000,
  });

  if (isAuthError(universes.error) || isAuthError(runs.error)) return <AuthErrorBox />;

  const selectedFeatures = FEATURES.filter((f) => features[f]);
  const isCustom = universeId === CUSTOM || universeId === "";
  const customList = customSymbols.split(",").map((s) => s.trim()).filter(Boolean);
  const canTrain = selectedFeatures.length > 0 && (!isCustom || customList.length > 0);

  const runTraining = async () => {
    setRunning(true);
    setRunError("");
    setResult(null);
    const payload: Record<string, unknown> = {
      model_family: modelFamily,
      features: selectedFeatures,
      horizon: Math.max(1, parseInt(horizon, 10) || 1),
    };
    if (isCustom) payload.symbols = customList;
    else payload.universe_id = universeId;
    try {
      const r = await apiFetch<Run>("/api/training/run", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setResult(r);
      queryClient.invalidateQueries({ queryKey: ["training"] });
    } catch (e: unknown) {
      setRunError(`Training failed: ${apiError(e)}`);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div>
      <h2>Training</h2>
      <div className="cards">
        <div className="card">
          <h3>Run Training</h3>
          <div style={{ marginBottom: "var(--space-3)" }}>
            <label style={{ color: "var(--fg-muted)", display: "block", marginBottom: "var(--space-1)" }}>
              Universe
            </label>
            <select value={universeId} onChange={(e) => setUniverseId(e.target.value)} style={{ width: 260 }}>
              <option value={CUSTOM}>Custom symbols</option>
              {universes.data?.map((u) => (
                <option key={u.id} value={u.id}>{u.name} ({u.symbols.length} symbols)</option>
              ))}
            </select>
          </div>
          {isCustom && (
            <div style={{ marginBottom: "var(--space-3)" }}>
              <label style={{ color: "var(--fg-muted)", display: "block", marginBottom: "var(--space-1)" }}>
                Symbols (comma-separated)
              </label>
              <input
                type="text"
                value={customSymbols}
                onChange={(e) => setCustomSymbols(e.target.value)}
                placeholder="AAPL, MSFT, NVDA"
                style={{ width: 260 }}
              />
            </div>
          )}
          <div style={{ marginBottom: "var(--space-3)" }}>
            <label style={{ color: "var(--fg-muted)", display: "block", marginBottom: "var(--space-1)" }}>
              Model family
            </label>
            <select value={modelFamily} onChange={(e) => setModelFamily(e.target.value)} style={{ width: 260 }}>
              <option value="logistic_regression">Logistic Regression</option>
              <option value="random_forest">Random Forest</option>
            </select>
          </div>
          <div style={{ marginBottom: "var(--space-3)" }}>
            <label style={{ color: "var(--fg-muted)", display: "block", marginBottom: "var(--space-1)" }}>
              Features
            </label>
            {FEATURES.map((f) => (
              <label key={f} style={{ display: "inline-flex", alignItems: "center", marginRight: "var(--space-3)", color: "var(--fg)" }}>
                <input
                  type="checkbox"
                  checked={!!features[f]}
                  onChange={(e) => setFeatures({ ...features, [f]: e.target.checked })}
                />
                {f.replace(/_/g, " ")}
              </label>
            ))}
          </div>
          <div style={{ marginBottom: "var(--space-3)" }}>
            <label style={{ color: "var(--fg-muted)", display: "block", marginBottom: "var(--space-1)" }}>
              Horizon (days ahead)
            </label>
            <input type="number" min={1} value={horizon} onChange={(e) => setHorizon(e.target.value)} style={{ width: 120 }} />
          </div>
          {runError && <div className="error-box">{runError}</div>}
          {result && (
            <div style={{ marginBottom: "var(--space-3)" }}>
              {statusPill(String(result.status ?? ""))}
              <span className="mono" style={{ marginLeft: "var(--space-2)", color: "var(--fg-muted)" }}>
                run {String(result.id ?? "").slice(0, 10)}
              </span>
              {result.model_id && (
                <span style={{ marginLeft: "var(--space-2)" }}>
                  model <Link to="/models" className="mono">{String(result.model_id).slice(0, 10)}</Link>
                </span>
              )}
              {result.error && <p className="fg-muted" style={{ marginTop: "var(--space-2)" }}>{result.error}</p>}
            </div>
          )}
          <button onClick={runTraining} disabled={running || !canTrain} style={{ marginTop: "var(--space-2)" }}>
            {running ? "Training..." : canTrain ? "Train" : selectedFeatures.length === 0 ? "Select at least one feature" : "Enter symbols"}
          </button>
        </div>
      </div>

      <h3>History</h3>
      {runs.isLoading ? (
        <div className="skeleton" style={{ height: 200 }} />
      ) : runs.error ? (
        <div className="error-box">{String(runs.error)}</div>
      ) : runs.data && runs.data.length > 0 ? (
        <table>
          <thead>
            <tr><th>ID</th><th>Symbols</th><th>Family</th><th>Features</th><th>Horizon</th><th>Status</th><th>Model</th><th>Metrics</th></tr>
          </thead>
          <tbody>
            {runs.data.map((r) => {
              const rid = String(r.id ?? "");
              const expanded = expandedId === rid;
              return (
                <Fragment key={rid}>
                  <tr onClick={() => setExpandedId(expanded ? null : rid)} style={{ cursor: "pointer" }}>
                    <td className="mono">{rid.slice(0, 10)}</td>
                    <td className="mono">{(r.symbols ?? []).join(", ").slice(0, 60) || "—"}</td>
                    <td>{String(r.model_family ?? "").replace(/_/g, " ")}</td>
                    <td>{(r.features ?? []).join(", ") || "—"}</td>
                    <td>{r.horizon ?? "—"}</td>
                    <td>{statusPill(String(r.status ?? ""))}</td>
                    <td>{r.model_id ? <Link to="/models" className="mono">{String(r.model_id).slice(0, 10)}</Link> : "—"}</td>
                    <td className="mono">{fmtMetrics(r.metrics)}</td>
                  </tr>
                  {expanded && (
                    <tr>
                      <td colSpan={8} style={{ background: "var(--surface-raised)" }}>
                        {r.error ? (
                          <div className="error-box" style={{ marginBottom: "var(--space-2)" }}>{r.error}</div>
                        ) : null}
                        <div className="mono" style={{ color: "var(--fg-muted)", whiteSpace: "pre-wrap", wordBreak: "break-all" }}>
                          {JSON.stringify(r, null, 2)}
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      ) : (
        <div className="empty-state"><p>No training runs yet — start one above.</p></div>
      )}
    </div>
  );
}
