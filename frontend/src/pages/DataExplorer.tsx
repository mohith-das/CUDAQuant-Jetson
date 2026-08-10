import { useState, useRef, useEffect } from "react";
import { createChart } from "lightweight-charts";
import { apiFetch } from "../api";

export default function DataExplorer() {
  const [symbol, setSymbol] = useState("AAPL");
  const [bars, setBars] = useState<Array<Record<string,unknown>>>([]);
  const chartRef = useRef<HTMLDivElement>(null);

  const fetchData = async () => {
    const data = await apiFetch<Array<Record<string,unknown>>>(`/api/data/bars?symbol=${symbol}&days=5&frequency=5m`);
    setBars(data);
  };

  useEffect(() => { fetchData(); }, [symbol]);

  useEffect(() => {
    if (!chartRef.current || bars.length === 0) return;
    const chart = createChart(chartRef.current, { width: chartRef.current.clientWidth, height: 400 });
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const candleSeries = (chart as any).addCandlestickSeries();
    const data = bars.map((b: Record<string,unknown>) => ({
      time: (new Date(b.timestamp as string).getTime() / 1000) as any,
      open: b.open as number,
      high: b.high as number,
      low: b.low as number,
      close: b.close as number,
    }));
    candleSeries.setData(data);
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [bars]);

  return (
    <div>
      <h2>Data Explorer</h2>
      <div style={{ marginBottom: 16 }}>
        <label>Symbol: </label>
        <select value={symbol} onChange={(e) => setSymbol(e.target.value)}>
          {["AAPL","MSFT","GOOGL","AMZN","SPY","QQQ"].map(s => <option key={s}>{s}</option>)}
        </select>
        <button onClick={fetchData} style={{ marginLeft: 8 }}>Fetch</button>
      </div>
      <div ref={chartRef} style={{ width: "100%", minHeight: 400 }} />
    </div>
  );
}
