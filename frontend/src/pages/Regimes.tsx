import { useState } from "react";
import { apiFetch } from "../api";

export default function Regimes() {
  const [result, setResult] = useState<Record<string,unknown> | null>(null);
  const [loading, setLoading] = useState(false);

  const detect = async () => {
    setLoading(true);
    const r = await apiFetch<Record<string,unknown>>("/api/regimes/detect", {
      method: "POST",
      body: JSON.stringify({ symbols: ["AAPL"], days: 30, frequency: "5m" }),
    });
    setResult(r);
    setLoading(false);
  };

  return (
    <div>
      <h2>Regime Detection</h2>
      <button onClick={detect} disabled={loading}>{loading ? "Running..." : "Run Detection"}</button>
      {result && (
        <div style={{ marginTop: 16 }}>
          <h3>Distribution</h3>
          <pre>{JSON.stringify(result.distribution, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
