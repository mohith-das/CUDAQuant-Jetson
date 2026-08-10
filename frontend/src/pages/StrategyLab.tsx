import { useState, useRef, useEffect } from "react";
import { createChart } from "lightweight-charts";
import { apiFetch } from "../api";
import { useQuery } from "@tanstack/react-query";

export default function StrategyLab() {
  const { data: strats } = useQuery({ queryKey: ["strategies"], queryFn: () => apiFetch<Record<string,unknown>>("/api/strategies/") });
  const [selected, setSelected] = useState("intraday_momentum");
  const [params, setParams] = useState<Record<string,string>>({ lookback: "20" });
  const [result, setResult] = useState<Record<string,unknown> | null>(null);
  const chartRef = useRef<HTMLDivElement>(null);

  const runBacktest = async () => {
    const p: Record<string,number> = {};
    Object.entries(params).forEach(([k,v]) => { p[k] = Number(v) || 0; });
    const r = await apiFetch<Record<string,unknown>>("/api/backtests/run", {
      method: "POST",
      body: JSON.stringify({ strategy: selected, params: p, symbols: ["AAPL"], days: 30, frequency: "5m" }),
    });
    setResult(r);
  };

  useEffect(() => {
    if (!chartRef.current || !result?.equity_curve) return;
    const chart = createChart(chartRef.current, { width: chartRef.current.clientWidth, height: 300 });
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const line = (chart as any).addLineSeries({ color: "#2962FF" });
    const curve = (result.equity_curve as number[]).map((v, i) => ({ time: i as any, value: v }));
    line.setData(curve);
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [result]);

  const stratData = strats?.[selected] as Record<string,unknown> | undefined;
  const schema = stratData?.parameters as Record<string, {default?: number; type?: string}> | undefined;

  return (
    <div>
      <h2>Strategy Lab</h2>
      <div className="cards">
        <div className="card">
          <h3>Strategy</h3>
          <select value={selected} onChange={(e) => setSelected(e.target.value)}>
            {strats && Object.keys(strats).map(s => <option key={s}>{s}</option>)}
          </select>
          {schema && Object.entries(schema).map(([name, info]) => (
            <div key={name} style={{ marginTop: 8 }}>
              <label>{name} ({info?.type}): </label>
              <input
                type="number"
                value={params[name] || info?.default || ""}
                onChange={(e) => setParams({...params, [name]: e.target.value})}
                style={{ width: 80 }}
              />
            </div>
          ))}
          <button onClick={runBacktest} style={{ marginTop: 12 }}>Run Backtest</button>
        </div>
        <div className="card">
          <h3>Metrics</h3>
          {result?.metrics ? (
            <table>
              <tbody>
                {Object.entries(result.metrics as Record<string,unknown>).map(([k,v]) => (
                  <tr key={k}><td>{k}</td><td>{typeof v === "number" ? v.toFixed(4) : String(v ?? "")}</td></tr>
                ))}
              </tbody>
            </table>
          ) : <p>Run a backtest to see metrics</p>}
        </div>
      </div>
      {!!result?.equity_curve && (
        <div style={{ marginTop: 16 }}>
          <h3>Equity Curve</h3>
          <div ref={chartRef} style={{ width: "100%", minHeight: 300 }} />
        </div>
      )}
    </div>
  );
}
