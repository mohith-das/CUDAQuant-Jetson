import { useState } from "react";
import { apiFetch } from "../api";

export default function Regimes() {
  const [result, setResult] = useState<Record<string,unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const detect = async () => {
    setLoading(true);
    setError("");
    try {
      const r = await apiFetch<Record<string,unknown>>("/api/regimes/detect", {
        method: "POST", body: JSON.stringify({ symbols: ["AAPL"], days: 30, frequency: "5m" }),
      });
      setResult(r);
    } catch (e: unknown) {
      setError(`Detection failed: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  const regimeColor = (r: string) => {
    if (r.includes("high_vol")) return "negative";
    if (r.includes("low_vol")) return "positive";
    return "fg-muted";
  };

  return (
    <div>
      <h2>Regime Detection</h2>
      <button onClick={detect} disabled={loading} style={{marginBottom:"var(--space-4)"}}>
        {loading ? "Running..." : "Run Detection"}
      </button>
      {error && <div className="error-box">{error}</div>}
      {loading && <div className="skeleton" style={{height:100}} />}
      {result && (
        <div className="card">
          <h3>Distribution</h3>
          <div style={{display:"flex",gap:"var(--space-4)",flexWrap:"wrap"}}>
            {Object.entries(result.distribution as Record<string,number>||{}).map(([k,v]) => (
              <div key={k} style={{textAlign:"center"}}>
                <p className="mono" style={{fontSize:"var(--text-metric)",color:`var(--${regimeColor(k)})`}}>{String(v)}</p>
                <p style={{color:"var(--fg-muted)",fontSize:"var(--text-eyebrow)"}}>{k.replace(/_/g," ")}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
