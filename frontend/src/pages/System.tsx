import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../api";

export default function System() {
  const { data: system, isLoading, error } = useQuery({
    queryKey: ["system"], queryFn: () => apiFetch<Record<string,unknown>>("/api/system/"), refetchInterval: 10000,
  });
  const { data: dispatch } = useQuery({
    queryKey: ["dispatch-stats"], queryFn: () => apiFetch<Record<string,unknown>>("/api/system/dispatch-stats"), refetchInterval: 10000,
  });

  if (error) return <div className="error-box">Cannot load system info — {String(error)}</div>;

  return (
    <div>
      <h2>System</h2>
      <div className="cards">
        <div className="card">
          <h3>Runtime</h3>
          {isLoading ? <div className="skeleton" style={{height:60}}/> : <>
            <p>Version: <span className="mono">{String(system?.version ?? "?")}</span></p>
            <p>Uptime: <span className="mono">{String(system?.uptime_seconds ? `${Number(system.uptime_seconds).toFixed(0)}s` : "?")}</span></p>
            <p>Mode: <span className="pill pill-accent">{String(system?.trading_mode ?? "?")}</span></p>
          </>}
        </div>
        <div className="card">
          <h3>GPU</h3>
          {isLoading ? <div className="skeleton" style={{height:60}}/> : <>
            <p>Config: <span className={`pill ${system?.cuda_enabled ? "pill-positive" : "pill-negative"}`}>{system?.cuda_enabled ? "Enabled" : "Disabled"}</span></p>
            <p>Features: <span className={`pill ${system?.gpu_active ? "pill-positive" : "pill-negative"}`}>{system?.gpu_active ? "Active" : "Inactive"}</span></p>
            <p>ML: <span className={`pill ${system?.ml_gpu_active ? "pill-positive" : "pill-negative"}`}>{system?.ml_gpu_active ? "Active" : "Inactive"}</span></p>
          </>}
        </div>
        <div className="card">
          <h3>Integrations</h3>
          {isLoading ? <div className="skeleton" style={{height:60}}/> : <>
            <p>MCP: <span className={`pill ${system?.mcp_installed ? "pill-positive" : "pill-negative"}`}>{system?.mcp_installed ? "Installed" : "Not installed"}</span></p>
            <p>Telegram: <span className={`pill ${system?.telegram_configured ? "pill-positive" : "pill-negative"}`}>{system?.telegram_configured ? "Configured" : "Not configured"}</span></p>
          </>}
        </div>
        <div className="card">
          <h3>Dispatch Stats</h3>
          {dispatch ? (
            <table>
              <thead><tr><th>Backend</th><th>Function</th><th className="mono">Count</th></tr></thead>
              <tbody>
                {Object.entries(dispatch.gpu_calls as Record<string,number>||{}).map(([k,v]) => (
                  <tr key={"gpu_"+k}><td><span className="pill pill-positive">GPU</span></td><td>{k}</td><td className="mono">{String(v)}</td></tr>
                ))}
                {Object.entries(dispatch.cpu_calls as Record<string,number>||{}).map(([k,v]) => (
                  <tr key={"cpu_"+k}><td><span className="pill pill-accent">CPU</span></td><td>{k}</td><td className="mono">{String(v)}</td></tr>
                ))}
              </tbody>
            </table>
          ) : <div className="skeleton" style={{height:60}}/>}
        </div>
      </div>
    </div>
  );
}
