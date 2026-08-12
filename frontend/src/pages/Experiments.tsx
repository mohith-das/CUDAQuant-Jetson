import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../api";
import { Link } from "react-router-dom";
import { AuthErrorBox, isAuthError } from "../AuthErrorBox";

export default function Experiments() {
  const { data: exps, isLoading, error } = useQuery({
    queryKey: ["experiments"],
    queryFn: () => apiFetch<Array<Record<string,unknown>>>("/api/experiments/"),
    refetchInterval: 5000,
  });

  if (isAuthError(error)) return <AuthErrorBox />;
  if (isLoading) return <div className="skeleton" style={{height:200}} />;
  if (error) return <div className="error-box">{String(error)}</div>;

  const fmtMetrics = (m: unknown) => {
    if (!m || (typeof m === "object" && Object.keys(m as object).length === 0)) return "—";
    return JSON.stringify(m).slice(0, 60);
  };

  const originPill = (o: string) => {
    const cls = o === "llm" ? "pill-accent" : o === "llm_fallback" ? "pill-warning" : "";
    return <span className={`pill ${cls}`}>{o}</span>;
  };

  return (
    <div>
      <h2>Experiments</h2>
      {exps && exps.length > 0 ? (
        <table>
          <thead><tr><th>ID</th><th>Hypothesis</th><th>Status</th><th>Origin</th><th>Metrics</th></tr></thead>
          <tbody>
            {exps.map((e: Record<string,unknown>) => (
              <tr key={e.experiment_id as string}>
                <td className="mono">{String(e.experiment_id).slice(0,10)}</td>
                <td>{String(e.hypothesis ?? "").slice(0, 60)}</td>
                <td>{String(e.status)}</td>
                <td>{originPill(String(e.origin))}</td>
                <td className="mono">{fmtMetrics(e.metrics)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className="empty-state">
          <p>No experiments yet.</p>
          <Link to="/welcome"><button style={{marginTop:"var(--space-2)"}}>Create in Welcome</button></Link>
        </div>
      )}
    </div>
  );
}
