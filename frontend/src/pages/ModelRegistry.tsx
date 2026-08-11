import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../api";
import { useState } from "react";

export default function ModelRegistry() {
  const { data: models, isLoading, error } = useQuery({
    queryKey: ["models"],
    queryFn: () => apiFetch<Array<Record<string,unknown>>>("/api/models/"),
    refetchInterval: 10000,
  });
  const [actionMsg, setActionMsg] = useState("");

  if (error) return <div className="error-box">Failed to load models — {String(error)}</div>;
  if (isLoading) return <div className="skeleton" style={{height:200}} />;

  const promote = async (id: string) => {
    try {
      await apiFetch(`/api/models/${id}/promote`, {method:"POST"});
      setActionMsg(`Promoted ${id}`);
    } catch (e: unknown) {
      setActionMsg(`Error: ${(e as Error).message}`);
    }
  };

  const statusPill = (s: string) => {
    const cls = s === "champion" ? "pill-positive" : s === "challenger" ? "pill-accent" : s === "candidate" ? "pill" : s === "retired" ? "pill-warning" : "pill";
    return <span className={`pill ${cls}`} style={{color: s==="retired"?"var(--fg-muted)":undefined}}>{s}</span>;
  };

  return (
    <div>
      <h2>Model Registry</h2>
      {actionMsg && <p className="mono" style={{marginBottom:"var(--space-2)",color:"var(--fg-muted)"}}>{actionMsg}</p>}
      {models && models.length > 0 ? (
        <table>
          <thead><tr><th>ID</th><th>Family</th><th>Version</th><th>Status</th><th>Actions</th></tr></thead>
          <tbody>
            {models.map((m: Record<string,unknown>) => (
              <tr key={m.model_id as string}>
                <td className="mono">{String(m.model_id).slice(0,12)}</td>
                <td>{m.family as string}</td>
                <td className="mono">{String(m.version)}</td>
                <td>{statusPill(m.status as string)}</td>
                <td>
                  {(m.status === "candidate" || m.status === "challenger") && (
                    <button onClick={() => promote(m.model_id as string)}>
                      {m.status === "challenger" ? "Make Champion" : "Promote"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className="empty-state">No models registered yet. Train a model via scheduler retrain job.</div>
      )}
    </div>
  );
}
