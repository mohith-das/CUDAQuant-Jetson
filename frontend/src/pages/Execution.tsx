import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../api";
import { useState } from "react";

export default function Execution() {
  const { data: risk } = useQuery({ queryKey: ["risk"], queryFn: () => apiFetch<Record<string,unknown>>("/api/risk/"), refetchInterval: 5000 });
  const { data: account } = useQuery({ queryKey: ["account"], queryFn: () => apiFetch<Record<string,unknown>>("/api/execution/account"), refetchInterval: 10000 });
  const { data: positions } = useQuery({ queryKey: ["positions"], queryFn: () => apiFetch<Array<Record<string,unknown>>>("/api/execution/positions"), refetchInterval: 10000 });
  const { data: orders } = useQuery({ queryKey: ["orders"], queryFn: () => apiFetch<Array<Record<string,unknown>>>("/api/execution/orders"), refetchInterval: 10000 });

  const [symbol, setSymbol] = useState("AAPL");
  const [qty, setQty] = useState(1);
  const [side, setSide] = useState("buy");
  const [msg, setMsg] = useState("");

  const ks = risk as Record<string,unknown> | undefined;
  const disabled = ks?.kill_switch_engaged || !ks?.broker_connected;

  const submit = async () => {
    setMsg("");
    try {
      const r = await apiFetch<Record<string,unknown>>("/api/execution/orders", {
        method: "POST",
        body: JSON.stringify({ symbol, side, qty: Number(qty), order_type: "market" }),
      });
      setMsg(`Order submitted: ${r.order_id}`);
    } catch (e: unknown) {
      setMsg(`Error: ${(e as Error).message}`);
    }
  };

  return (
    <div>
      <h2>Execution</h2>
      <div className="cards">
        <div className="card">
          <h3>Account</h3>
          {account ? <><p>Cash: ${(account.cash as number)?.toFixed(2)}</p>
            <p>Portfolio: ${(account.portfolio_value as number)?.toFixed(2)}</p>
            <p>Buying Power: ${(account.buying_power as number)?.toFixed(2)}</p></> : <p>No broker configured</p>}
        </div>
        <div className="card">
          <h3>Positions</h3>
          {positions && positions.length > 0 ? (
            <table><thead><tr><th>Symbol</th><th>Qty</th><th>P&L</th></tr></thead>
              <tbody>{positions.map((p: Record<string,unknown>) => (
                <tr key={p.symbol as string}><td>{p.symbol as string}</td><td>{p.qty as number}</td><td>{Number(p.unrealized_pnl).toFixed(2)}</td></tr>
              ))}</tbody></table>
          ) : <p>No open positions</p>}
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <h3>Order Ticket {disabled && "(Disabled — kill switch engaged or no broker)"}</h3>
        {!disabled && (
          <div>
            <select value={symbol} onChange={(e) => setSymbol(e.target.value)}>
              {["AAPL","MSFT","GOOGL","SPY"].map(s => <option key={s}>{s}</option>)}
            </select>
            <select value={side} onChange={(e) => setSide(e.target.value)}>
              <option value="buy">Buy</option><option value="sell">Sell</option>
            </select>
            <input type="number" value={qty} onChange={(e) => setQty(Number(e.target.value))} min={1} style={{ width: 80 }} />
            <button onClick={submit}>Submit Paper Order</button>
          </div>
        )}
        {msg && <p style={{ marginTop: 8 }}>{msg}</p>}
      </div>

      <h3 style={{ marginTop: 16 }}>Order History</h3>
      {orders && orders.length > 0 ? (
        <table><thead><tr><th>ID</th><th>Symbol</th><th>Side</th><th>Qty</th><th>Status</th></tr></thead>
          <tbody>{orders.map((o: Record<string,unknown>) => (
            <tr key={o.id as string}><td>{o.id as string}</td><td>{o.symbol as string}</td><td>{o.side as string}</td><td>{o.qty as string}</td><td>{o.status as string}</td></tr>
          ))}</tbody></table>
      ) : <p>No orders yet</p>}
    </div>
  );
}
