import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../api";

export default function System() {
  const { data: system } = useQuery({ queryKey: ["system"], queryFn: () => apiFetch<Record<string,unknown>>("/api/system/"), refetchInterval: 10000 });
  const { data: dispatch } = useQuery({ queryKey: ["dispatch-stats"], queryFn: () => apiFetch<Record<string,unknown>>("/api/system/dispatch-stats"), refetchInterval: 10000 });

  return (
    <div>
      <h2>System</h2>
      <div className="cards">
        <div className="card">
          <h3>Runtime</h3>
          <p>Version: {system?.version as string}</p>
          <p>Uptime: {system?.uptime_seconds ? `${Number(system.uptime_seconds).toFixed(0)}s` : "—"}</p>
          <p>Mode: {system?.trading_mode as string}</p>
        </div>
        <div className="card">
          <h3>GPU</h3>
          <p>Config: {system?.cuda_enabled ? "Enabled" : "Disabled"}</p>
          <p>Features: {system?.gpu_active ? "✓ Active" : "✗ Inactive"}</p>
          <p>ML: {system?.ml_gpu_active ? "✓ Active" : "✗ Inactive"}</p>
        </div>
        <div className="card">
          <h3>Dispatch Stats</h3>
          {dispatch && (
            <pre style={{ fontSize: 12 }}>{JSON.stringify(dispatch, null, 2)}</pre>
          )}
        </div>
      </div>
    </div>
  );
}
