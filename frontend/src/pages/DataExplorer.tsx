import { useState, useRef, useEffect } from "react";
import { createChart } from "lightweight-charts";
import { apiFetch } from "../api";

export default function DataExplorer() {
  const [symbol, setSymbol] = useState("AAPL");
  const [bars, setBars] = useState<Array<Record<string,unknown>>>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<ReturnType<typeof createChart> | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await apiFetch<Array<Record<string,unknown>>>(`/api/data/bars?symbol=${symbol}&days=5&frequency=5m`);
      setBars(data);
      if (data.length === 0) setError("No data returned for this symbol");
    } catch (e: unknown) {
      setError(`Fetch failed: ${(e as Error).message}`);
      setBars([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, [symbol]);

  useEffect(() => {
    if (!chartRef.current || bars.length === 0) return;
    if (chartInstance.current) { chartInstance.current.remove(); chartInstance.current = null; }

    const chart = createChart(chartRef.current, {
      width: chartRef.current.clientWidth,
      height: 450,
      layout: { background: { color: "#0B0D11" }, textColor: "#8B94A3" },
      grid: { vertLines: { color: "#262B33" }, horzLines: { color: "#262B33" } },
      crosshair: { mode: 0 },
      rightPriceScale: { borderColor: "#383F4A" },
      timeScale: { borderColor: "#383F4A", timeVisible: true },
    });
    chartInstance.current = chart;

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const candleSeries = (chart as any).addCandlestickSeries({
      upColor: "#1FAE5C", downColor: "#E5484D", borderUpColor: "#1FAE5C",
      borderDownColor: "#E5484D", wickUpColor: "#1FAE5C", wickDownColor: "#E5484D",
    });
    const data = bars.map((b: Record<string,unknown>) => ({
      time: (new Date(b.timestamp as string).getTime() / 1000) as any,
      open: b.open as number, high: b.high as number,
      low: b.low as number, close: b.close as number,
    }));
    candleSeries.setData(data);
    chart.timeScale().fitContent();
    return () => { chart.remove(); chartInstance.current = null; };
  }, [bars]);

  return (
    <div>
      <h2>Data Explorer</h2>
      <div style={{ marginBottom: "var(--space-4)", display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
        <label style={{ color: "var(--fg-muted)" }}>Symbol:</label>
        <select value={symbol} onChange={(e) => setSymbol(e.target.value)}>
          {["AAPL","MSFT","GOOGL","AMZN","SPY","QQQ","BTC/USD"].map(s => <option key={s}>{s}</option>)}
        </select>
        <button onClick={fetchData} disabled={loading}>{loading ? "Loading..." : "Fetch"}</button>
      </div>
      {error && <div className="error-box">{error}</div>}
      {loading && <div className="skeleton" style={{ width: "100%", height: 450 }} />}
      {!loading && !error && bars.length === 0 && (
        <div className="empty-state">Click Fetch to load {symbol} price data</div>
      )}
      <div ref={chartRef} style={{ width: "100%", minHeight: 450 }} />
    </div>
  );
}
