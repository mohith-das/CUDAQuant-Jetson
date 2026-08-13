import { useQuery } from "@tanstack/react-query";
import { apiFetch, queryClient } from "../api";
import { useState } from "react";

// apiFetch throws `API 403: {"detail": "..."}` — surface the detail, not the raw body.
function apiDetail(e: unknown): string {
  const msg = e instanceof Error ? e.message : String(e);
  const m = /^API 403:\s*(.*)$/s.exec(msg);
  if (m) {
    try {
      const body = JSON.parse(m[1]) as { detail?: unknown };
      if (typeof body.detail === "string") return body.detail;
    } catch {
      // not JSON — fall through to the raw message
    }
  }
  return msg;
}

export default function Execution() {
  const { data: risk, error: riskError } = useQuery({
    queryKey: ["risk"], queryFn: () => apiFetch<Record<string,unknown>>("/api/risk/"), refetchInterval: 5000,
  });
  const { data: account, isLoading: acctLoading } = useQuery({
    queryKey: ["account"], queryFn: () => apiFetch<Record<string,unknown>>("/api/execution/account"), refetchInterval: 10000,
  });
  const { data: positions, isLoading: posLoading } = useQuery({
    queryKey: ["positions"], queryFn: () => apiFetch<Array<Record<string,unknown>>>("/api/execution/positions"), refetchInterval: 10000,
  });
  const { data: orders, isLoading: ordLoading } = useQuery({
    queryKey: ["orders"], queryFn: () => apiFetch<Array<Record<string,unknown>>>("/api/execution/orders"), refetchInterval: 10000,
  });

  const [symbol, setSymbol] = useState("AAPL");
  const [qty, setQty] = useState(1);
  const [side, setSide] = useState("buy");
  const [msg, setMsg] = useState("");

  const [liveConfirm, setLiveConfirm] = useState("");
  const [modeMsg, setModeMsg] = useState("");
  const [modeErr, setModeErr] = useState("");

  const ks = risk as Record<string,unknown> | undefined;
  const killEngaged = ks?.kill_switch_engaged as boolean;
  const brokerOk = ks?.broker_connected as boolean;
  const tradingMode = ks?.trading_mode as string | undefined;
  const desiredMode = ks?.desired_mode as string | undefined;
  const modeReason = ks?.mode_reason as string | null | undefined;
  const envLiveEligible = ks?.env_live_eligible as boolean | undefined;
  const disabled = killEngaged || !brokerOk;
  const disableReason = killEngaged
    ? "Kill switch is engaged"
    : !brokerOk
    ? "No broker connected"
    : "";

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

  const switchToLive = async () => {
    setModeMsg(""); setModeErr("");
    try {
      const r = await apiFetch<Record<string,unknown>>("/api/risk/trading-mode", {
        method: "PUT",
        body: JSON.stringify({ mode: "live", confirm: liveConfirm }),
      });
      await queryClient.invalidateQueries({ queryKey: ["risk"] });
      setLiveConfirm("");
      setModeMsg(String(r.message ?? "switched to live mode"));
    } catch (e: unknown) {
      setModeErr(apiDetail(e));
    }
  };

  const switchToPaper = async () => {
    setModeMsg(""); setModeErr("");
    try {
      const r = await apiFetch<Record<string,unknown>>("/api/risk/trading-mode", {
        method: "PUT",
        body: JSON.stringify({ mode: "paper" }),
      });
      await queryClient.invalidateQueries({ queryKey: ["risk"] });
      setModeMsg(String(r.message ?? "switched to paper mode"));
    } catch (e: unknown) {
      setModeErr(apiDetail(e));
    }
  };

  if (riskError) return <div className="error-box">Cannot connect to API — check auth token</div>;

  return (
    <div>
      <h2>Execution</h2>

      <div className="card" style={{ marginBottom: "var(--space-6)" }}>
        <h3>Trading Mode</h3>
        <p>
          Mode:{" "}
          {tradingMode === "live" ? (
            <span className="pill pill-warning">LIVE</span>
          ) : tradingMode === "paper" ? (
            <span className="pill pill-positive">Paper</span>
          ) : (
            <span className="pill">—</span>
          )}
        </p>
        {modeReason ? (
          <p className="warning-text" style={{ marginTop: "var(--space-2)" }}>
            Desired {String(desiredMode ?? "?")} but running {String(tradingMode ?? "?")} — {modeReason}
          </p>
        ) : null}
        {tradingMode === "paper" ? (
          <div style={{ marginTop: "var(--space-3)" }}>
            {envLiveEligible === false ? (
              <p className="fg-muted" style={{ fontSize: "var(--text-eyebrow)", marginBottom: "var(--space-2)" }}>
                Live unavailable — set TRADING_MODE=live and ENABLE_LIVE_TRADING=I_UNDERSTAND_LIVE_TRADING_RISK in .env
              </p>
            ) : null}
            <input
              type="text"
              placeholder='Type "LIVE" to confirm'
              value={liveConfirm}
              onChange={(e) => setLiveConfirm(e.target.value)}
            />
            <button className="btn-danger" onClick={switchToLive} disabled={liveConfirm !== "LIVE"}>
              Switch to Live
            </button>
          </div>
        ) : tradingMode === "live" ? (
          <div style={{ marginTop: "var(--space-3)" }}>
            <button onClick={switchToPaper}>Switch to Paper</button>
          </div>
        ) : null}
        {modeErr && <p className="mono negative" style={{ marginTop: "var(--space-2)" }}>{modeErr}</p>}
        {modeMsg && <p className="mono" style={{ marginTop: "var(--space-2)" }}>{modeMsg}</p>}
        <p className="fg-muted" style={{ fontSize: "var(--text-eyebrow)", marginTop: "var(--space-3)" }}>
          Mode persists across restarts. Switching to live requires TRADING_MODE=live +
          ENABLE_LIVE_TRADING=I_UNDERSTAND_LIVE_TRADING_RISK in .env, a disarmed kill switch, and verified
          live broker credentials.
        </p>
      </div>

      <div className="cards">
        <div className="card">
          <h3>Account</h3>
          {acctLoading ? <div className="skeleton" style={{height:60}} /> :
           account ? <>
            <p className="mono">Cash: <span className="positive">${(account.cash as number)?.toFixed(2)}</span></p>
            <p>Portfolio: <span className="mono">${(account.portfolio_value as number)?.toFixed(2)}</span></p>
            <p>Buying Power: <span className="mono">${(account.buying_power as number)?.toFixed(2)}</span></p>
          </> : <p className="fg-muted">No broker configured — set ALPACA_API_KEY</p>}
        </div>
        <div className="card">
          <h3>Positions</h3>
          {posLoading ? <div className="skeleton" style={{height:60}} /> :
           positions && positions.length > 0 ? (
            <table><thead><tr><th>Symbol</th><th className="mono">Qty</th><th className="mono">P&L</th></tr></thead>
              <tbody>{positions.map((p: Record<string,unknown>) => (
                <tr key={p.symbol as string}><td>{p.symbol as string}</td>
                  <td className="mono">{String(p.qty)}</td>
                  <td className={`mono ${Number(p.unrealized_pnl) >= 0 ? "positive" : "negative"}`}>
                    ${Number(p.unrealized_pnl).toFixed(2)}</td></tr>
              ))}</tbody></table>
          ) : <p className="fg-muted">No open positions</p>}
        </div>
      </div>

      <div className="card" style={{ marginTop: "var(--space-4)" }}>
        <h3>Order Ticket {disabled ? <span className="pill pill-warning">DISABLED — {disableReason}</span> : null}</h3>
        {!disabled ? (
          <div style={{display:"flex", gap:"var(--space-2)", alignItems:"center", flexWrap:"wrap"}}>
            <select value={symbol} onChange={(e) => setSymbol(e.target.value)}>
              {["AAPL","MSFT","GOOGL","SPY","BTC/USD"].map(s => <option key={s}>{s}</option>)}
            </select>
            <select value={side} onChange={(e) => setSide(e.target.value)}>
              <option value="buy">Buy</option><option value="sell">Sell</option>
            </select>
            <input type="number" value={qty} onChange={(e) => setQty(Number(e.target.value))} min={0.001} step={0.001} style={{width:100}} />
            <button onClick={submit}>Submit Paper Order</button>
          </div>
        ) : null}
        {msg && <p style={{ marginTop: "var(--space-2)" }} className="mono">{msg}</p>}
      </div>

      <h3 style={{ marginTop: "var(--space-6)" }}>Order History</h3>
      {ordLoading ? <div className="skeleton" style={{height:80}} /> :
       orders && orders.length > 0 ? (
        <table><thead><tr><th>ID</th><th>Symbol</th><th>Side</th><th className="mono">Qty</th><th>Status</th></tr></thead>
          <tbody>{orders.map((o: Record<string,unknown>) => (
            <tr key={o.id as string}><td className="mono">{String(o.id).slice(0,12)}</td><td>{o.symbol as string}</td>
              <td className={o.side === "buy" ? "positive" : "negative"}>{o.side as string}</td>
              <td className="mono">{String(o.qty)}</td><td>{o.status as string}</td></tr>
          ))}</tbody></table>
      ) : <p className="fg-muted">No orders yet</p>}
    </div>
  );
}
