import { useState, useRef, useEffect } from "react";
import { createChart, CandlestickSeries } from "lightweight-charts";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../api";

interface Universe { id: string; name: string; symbols: string[]; }

const DEFAULT_SYMBOLS = ["AAPL","MSFT","GOOGL","AMZN","SPY","QQQ","BTC/USD"];

export default function DataExplorer() {
  const [symbol, setSymbol] = useState("AAPL");
  const [bars, setBars] = useState<Array<Record<string,unknown>>>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [universeId, setUniverseId] = useState("");
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<ReturnType<typeof createChart> | null>(null);

  const { data: universes, error: universesError } = useQuery({
    queryKey: ["universes"],
    queryFn: () => apiFetch<Universe[]>("/api/universe/"),
  });

  const activeUniverse = universes?.find((u) => u.id === universeId) ?? null;
  const symbolOptions =
    activeUniverse && activeUniverse.symbols.length > 0 ? activeUniverse.symbols : DEFAULT_SYMBOLS;

  // Keep the current symbol valid when a universe is selected.
  useEffect(() => {
    if (activeUniverse && activeUniverse.symbols.length > 0 && !activeUniverse.symbols.includes(symbol)) {
      setSymbol(activeUniverse.symbols[0]);
    }
  }, [activeUniverse?.id]);

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

    const candleSeries = chart.addSeries(CandlestickSeries, {
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
      <div style={{ marginBottom: "var(--space-4)", display: "flex", gap: "var(--space-2)", alignItems: "center", flexWrap: "wrap" }}>
        <label style={{ color: "var(--fg-muted)" }}>Universe:</label>
        <select value={universeId} onChange={(e) => setUniverseId(e.target.value)}>
          <option value="">All symbols</option>
          {(universes ?? []).map((u) => (
            <option key={u.id} value={u.id}>{u.name || "unnamed"}</option>
          ))}
        </select>
        {universesError && (
          <span style={{ color: "var(--fg-faint)", fontSize: "var(--text-eyebrow)" }}>Universe list unavailable</span>
        )}
        <label style={{ color: "var(--fg-muted)" }}>Symbol:</label>
        <select value={symbol} onChange={(e) => setSymbol(e.target.value)}>
          {symbolOptions.map(s => <option key={s}>{s}</option>)}
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
