import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../api";
import { useState } from "react";

export default function ModelComparison() {
  const { data: models, isLoading, error } = useQuery({
    queryKey: ["models"],
    queryFn: () => apiFetch<Array<Record<string,unknown>>>("/api/models/"),
    refetchInterval: 10000,
  });
  const [liveData, setLiveData] = useState<Record<string,unknown>>({});
  const [execConfirm, setExecConfirm] = useState("");

  if (error) return <div className="error-box">Failed to load models — {String(error)}</div>;
  if (isLoading) return <div className="skeleton" style={{height:300}} />;

  const groups: Record<string, Array<Record<string,unknown>>> = {};
  (models || []).forEach(m => { const s = String(m.status||""); if (!groups[s]) groups[s] = []; groups[s].push(m); });

  const promote = async (id: string) => {
    await apiFetch(`/api/models/${id}/promote`, {method:"POST"});
  };
  const fetchLive = async (id: string) => {
    try {
      const d = await apiFetch<Record<string,unknown>>(`/api/models/${id}/live-performance`);
      setLiveData(prev => ({...prev, [id]: d}));
    } catch (e: unknown) { /* ignore */ }
  };
  const enableExec = async () => {
    if (execConfirm !== "ENABLE") return;
    await apiFetch("/api/scheduler/auto-execute", {method:"PUT", body: JSON.stringify({confirm:"ENABLE"})});
    setExecConfirm("");
  };

  const statusPill = (s: string) => {
    const cls = s === "champion" ? "pill-positive" : s === "challenger" ? "pill-accent" : "pill-warning";
    return <span className={`pill ${cls}`}>{s}</span>;
  };

  return (
    <div>
      <h2>Model Comparison</h2>
      {Object.entries(groups).map(([status, ms]) => (
        <div key={status} style={{marginBottom:"var(--space-6)"}}>
          <h3>{status.charAt(0).toUpperCase()+status.slice(1)} ({ms.length})</h3>
          <div className="cards">
            {ms.map((m: Record<string,unknown>) => (
              <div className="card" key={m.model_id as string}>
                <p className="mono" style={{color:"var(--fg-muted)",fontSize:"var(--text-eyebrow)"}}>{String(m.model_id).slice(0,16)}</p>
                <p>{statusPill(status)} · {String(m.family ?? "")} v{String(m.version)}</p>
                {!!m.metrics && <p className="mono" style={{fontSize:"var(--text-body)",color:"var(--fg-muted)",marginTop:"var(--space-1)"}}>
                  {String(JSON.stringify(m.metrics)).slice(0,80)}</p>}
                <div style={{marginTop:"var(--space-2)",display:"flex",gap:"var(--space-1)",flexWrap:"wrap"}}>
                  {(status === "candidate" || status === "challenger") && (
                    <button onClick={() => promote(m.model_id as string)}>Promote</button>
                  )}
                  {status === "champion" && (
                    <button onClick={() => fetchLive(m.model_id as string)} style={{background:"var(--surface-raised)",color:"var(--fg-muted)",border:"1px solid var(--border)"}}>
                      Live Performance
                    </button>
                  )}
                </div>
                {!!liveData[m.model_id as string] && (
                  <pre style={{fontSize:"var(--text-eyebrow)",marginTop:"var(--space-2)"}}>
                    {JSON.stringify(liveData[m.model_id as string],null,2)}
                  </pre>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
      <div className="card" style={{marginTop:"var(--space-4)"}}>
        <h3>Enable Live Execution</h3>
        <p style={{color:"var(--fg-muted)",marginBottom:"var(--space-2)"}}>Requires typing ENABLE to confirm.</p>
        <input value={execConfirm} onChange={e => setExecConfirm(e.target.value)} placeholder='Type "ENABLE"' />
        <button onClick={enableExec} disabled={execConfirm !== "ENABLE"} className="btn-danger">Enable</button>
      </div>
    </div>
  );
}
