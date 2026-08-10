import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../api";
import { useState } from "react";

export default function Dashboard() {
  const { data: health } = useQuery({ queryKey: ["health"], queryFn: () => apiFetch<Record<string,unknown>>("/health"), refetchInterval: 5000 });
  const { data: readiness } = useQuery({ queryKey: ["readiness"], queryFn: () => apiFetch<Record<string,unknown>>("/readiness"), refetchInterval: 10000 });
  const { data: system } = useQuery({ queryKey: ["system"], queryFn: () => apiFetch<Record<string,unknown>>("/api/system/"), refetchInterval: 10000 });
  const { data: risk } = useQuery({ queryKey: ["risk"], queryFn: () => apiFetch<Record<string,unknown>>("/api/risk/"), refetchInterval: 5000 });
  const { data: dispatch } = useQuery({ queryKey: ["dispatch-stats"], queryFn: () => apiFetch<Record<string,unknown>>("/api/system/dispatch-stats"), refetchInterval: 10000 });

  const [ksConfirm, setKsConfirm] = useState("");

  const checks = readiness?.checks as Record<string,unknown> | undefined;
  const ks = risk as Record<string,unknown> | undefined;

  const killSwitch = async () => {
    if (ksConfirm !== "STOP") return;
    await apiFetch("/api/risk/kill-switch", { method: "POST", body: JSON.stringify({ confirm: "STOP" }) });
    setKsConfirm("");
  };

  return (
    <div>
      <h2>Dashboard</h2>
      <div className="cards">
        <div className="card">
          <h3>System</h3>
          <p>Status: {health?.status === "ok" ? "✓ Online" : "⚠ Unknown"}</p>
          <p>Uptime: {system ? `${(system.uptime_seconds as number).toFixed(0)}s` : "—"}</p>
          <p>Version: {String(health?.version ?? "")}</p>
        </div>
        <div className="card">
          <h3>GPU</h3>
          <p>Config: {checks?.cuda_enabled ? "Enabled" : "Disabled"}</p>
          <p>Features: {checks?.gpu_active ? "✓ Active" : "✗ Inactive"}</p>
          <p>ML: {checks?.ml_gpu_active ? "✓ Active" : "✗ Inactive"}</p>
        </div>
        <div className="card">
          <h3>Trading</h3>
          <p>Mode: <strong>{checks?.trading_mode as string}</strong></p>
          <p>Live: {checks?.live_trading_enabled ? "⚠ ENABLED" : "✓ Disabled"}</p>
          <p>Broker: {ks?.broker_connected ? "✓ Connected" : "✗ Disconnected"}</p>
        </div>
        <div className="card danger">
          <h3>Kill Switch</h3>
          <p className={ks?.kill_switch_engaged ? "danger-text" : "safe-text"}>
            {ks?.kill_switch_engaged ? "⚠ ENGAGED" : "✓ Disarmed"}
          </p>
          {ks?.kill_switch_reason ? <p>Reason: {String(ks.kill_switch_reason)}</p> : null}
          {!ks?.kill_switch_engaged && (
            <div style={{ marginTop: 8 }}>
              <input
                type="text"
                placeholder='Type "STOP" to confirm'
                value={ksConfirm}
                onChange={(e) => setKsConfirm(e.target.value)}
              />
              <button onClick={killSwitch} disabled={ksConfirm !== "STOP"} className="btn-danger">
                Engage Kill Switch
              </button>
            </div>
          )}
        </div>
      </div>

      <h3>GPU Dispatch Stats</h3>
      {dispatch && (
        <table>
          <thead><tr><th>Type</th><th>Count</th></tr></thead>
          <tbody>
            {Object.entries(dispatch.gpu_calls as Record<string,number> || {}).map(([k,v]) => (
              <tr key={k}><td>GPU: {k}</td><td>{v}</td></tr>
            ))}
            {Object.entries(dispatch.cpu_calls as Record<string,number> || {}).map(([k,v]) => (
              <tr key={k}><td>CPU: {k}</td><td>{v}</td></tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
