import { useState, useRef, useEffect } from "react";
import { createChart } from "lightweight-charts";
import { apiFetch } from "../api";
import { useQuery } from "@tanstack/react-query";

export default function StrategyLab() {
  const { data: strats, isLoading: stratsLoading, error: stratsError } = useQuery({
    queryKey: ["strategies"], queryFn: () => apiFetch<Record<string,unknown>>("/api/strategies/"),
  });
  const [selected, setSelected] = useState("intraday_momentum");
  const [params, setParams] = useState<Record<string,string>>({ lookback: "20" });
  const [result, setResult] = useState<Record<string,unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<ReturnType<typeof createChart> | null>(null);

  const stratNames = strats ? Object.keys(strats) : [];
  const stratData = strats?.[selected] as Record<string,unknown> | undefined;
  const schema = stratData?.parameters as Record<string, {default?: number; type?: string}> | undefined;

  useEffect(() => {
    if (schema && Object.keys(params).length === 0) {
      const defaults: Record<string,string> = {};
      for (const [name, info] of Object.entries(schema)) {
        if (info?.default !== undefined && info?.default !== null) {
          defaults[name] = String(info.default);
        }
      }
      if (Object.keys(defaults).length > 0) setParams(defaults);
    }
  }, [schema]);

  const runBacktest = async () => {
    setLoading(true);
    setError("");
    try {
      const p: Record<string,number> = {};
      Object.entries(params).forEach(([k,v]) => { p[k] = Number(v) || 0; });
      const r = await apiFetch<Record<string,unknown>>("/api/backtests/run", {
        method: "POST",
        body: JSON.stringify({ strategy: selected, params: p, symbols: ["AAPL"], days: 30, frequency: "5m" }),
      });
      setResult(r);
    } catch (e: unknown) {
      setError(`Backtest failed: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!chartRef.current || !result?.equity_curve) return;
    if (chartInstance.current) { chartInstance.current.remove(); chartInstance.current = null; }

    const chart = createChart(chartRef.current, {
      width: chartRef.current.clientWidth, height: 320,
      layout: { background: { color: "#0B0D11" }, textColor: "#8B94A3" },
      grid: { vertLines: { color: "#262B33" }, horzLines: { color: "#262B33" } },
      rightPriceScale: { borderColor: "#383F4A" },
      timeScale: { borderColor: "#383F4A" },
    });
    chartInstance.current = chart;

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const line = (chart as any).addLineSeries({
      color: "#2E9BFF", lineWidth: 2,
      lastValueVisible: true, priceLineVisible: false,
    });
    const area = (chart as any).addAreaSeries({
      lineColor: "#2E9BFF", topColor: "rgba(46, 155, 255, 0.15)",
      bottomColor: "rgba(46, 155, 255, 0.02)", lineWidth: 0,
    });
    const curve = (result.equity_curve as number[]).map((v, i) => ({ time: i as any, value: v }));
    line.setData(curve);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (line as any).createPriceLine({ price: curve[0]?.value ?? 100000, color: "#5B6472", lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: "Initial" });
    area.setData(curve);
    chart.timeScale().fitContent();
    return () => { chart.remove(); chartInstance.current = null; };
  }, [result]);

  if (stratsError) return <div className="error-box">Cannot load strategies — check API connection</div>;

  return (
    <div>
      <h2>Strategy Lab</h2>
      {stratsLoading ? (
        <div className="skeleton" style={{ height: 200 }} />
      ) : (
        <div className="cards">
          <div className="card">
            <h3>Strategy</h3>
            <select value={selected} onChange={(e) => { setSelected(e.target.value); setParams({}); setResult(null); }}>
              {stratNames.map(s => <option key={s}>{s}</option>)}
            </select>
            {schema && Object.entries(schema).map(([name, info]) => (
              <div key={name} style={{ marginTop: "var(--space-2)", display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                <label style={{ color: "var(--fg-muted)", minWidth: 140, fontSize: "var(--text-body)" }}>
                  {name.replace(/_/g, " ")} {info?.type ? `(${info.type})` : ""}
                </label>
                <input
                  type="number"
                  value={params[name] ?? ""}
                  onChange={(e) => setParams({...params, [name]: e.target.value})}
                  style={{ width: 100 }}
                  step={info?.type === "float" ? "0.1" : "1"}
                />
              </div>
            ))}
            <button onClick={runBacktest} disabled={loading} style={{ marginTop: "var(--space-3)" }}>
              {loading ? "Running..." : "Run Backtest"}
            </button>
          </div>
          <div className="card">
            <h3>Metrics</h3>
            {error && <div className="error-box">{error}</div>}
            {result?.metrics ? (
              <table>
                <tbody>
                  {Object.entries(result.metrics as Record<string,unknown>).map(([k,v]) => (
                    <tr key={k}><td style={{color:"var(--fg-muted)"}}>{k}</td>
                      <td className="mono">{typeof v === "number" ? v.toFixed(4) : String(v ?? "")}</td></tr>
                  ))}
                </tbody>
              </table>
            ) : <p className="fg-muted">Select a strategy and run a backtest to see metrics</p>}
          </div>
        </div>
      )}
      {loading && <div className="skeleton" style={{ width: "100%", height: 320, marginTop: "var(--space-4)" }} />}
      {!!result?.equity_curve && (
        <div style={{ marginTop: "var(--space-4)" }}>
          <h3>Equity Curve</h3>
          <div ref={chartRef} style={{ width: "100%", minHeight: 320 }} />
        </div>
      )}
    </div>
  );
}
