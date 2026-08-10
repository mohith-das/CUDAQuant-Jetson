import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiFetch, queryClient } from "../api";

interface Experiment {
  experiment_id: string;
  hypothesis: string;
  status: string;
  origin: string;
  created_at: string;
  metrics: Record<string, unknown> | null;
}

const PASSED_STATUSES = new Set(["backtest_passed","paper_candidate","paper_running","probation","production"]);
const FAILED_STATUSES = new Set(["failed","rejected"]);

export default function LLMInbox() {
  const { data: experiments, isLoading, error } = useQuery({
    queryKey: ["experiments"],
    queryFn: () => apiFetch<Experiment[]>("/api/experiments/"),
    refetchInterval: 30000,
  });
  const [running, setRunning] = useState(false);

  const llmExps = (experiments || []).filter(
    (e: Experiment) => e.origin === "llm" || e.origin === "llm_fallback"
  );
  const realLLM = llmExps.filter(e => e.origin === "llm");
  const fallbackLLM = llmExps.filter(e => e.origin === "llm_fallback");
  const passed = llmExps.filter(e => PASSED_STATUSES.has(e.status)).length;
  const failed = llmExps.filter(e => FAILED_STATUSES.has(e.status)).length;
  const pending = llmExps.length - passed - failed;

  const runAnalysis = async () => {
    setRunning(true);
    try {
      await apiFetch("/api/scheduler/jobs/llm_analyze/run-now", { method: "POST" });
      queryClient.invalidateQueries({ queryKey: ["experiments"] });
    } catch (e: unknown) { /* ignore */ }
    setRunning(false);
  };

  if (isLoading) return <div className="skeleton" style={{height:200}} />;
  if (error) return <div className="error-box">Cannot load experiments — {String(error)}</div>;

  return (
    <div>
      <h2>LLM Proposal Inbox</h2>
      <div className="cards">
        <div className="card">
          <h3>LLM Activity</h3>
          <p className="mono" style={{fontSize:"var(--text-metric)", color:"var(--accent)"}}>{llmExps.length}</p>
          <p style={{color:"var(--fg-muted)"}}>Total from LLM origin</p>
          <div style={{display:"flex",gap:"var(--space-4)",marginTop:"var(--space-2)"}}>
            <span><span className="pill pill-positive">{passed}</span> Passed</span>
            <span><span className="pill pill-negative">{failed}</span> Failed</span>
            <span><span className="pill pill-accent">{pending}</span> Pending</span>
          </div>
          <div style={{marginTop:"var(--space-2)",color:"var(--fg-faint)",fontSize:"var(--text-eyebrow)"}}>
            {realLLM.length} real LLM · {fallbackLLM.length} fallback (LLM unavailable)
          </div>
        </div>
        <div className="card">
          <h3>Budget</h3>
          <p style={{color:"var(--fg-muted)",fontSize:"var(--text-body)"}}>
            LLM budget is tracked server-side via LLMBudget. Check /api/system/ for counters.
          </p>
          <button onClick={runAnalysis} disabled={running} style={{marginTop:"var(--space-3)"}}>
            {running ? "Running..." : "Run Analysis Now"}
          </button>
        </div>
      </div>

      {llmExps.length === 0 ? (
        <div className="empty-state">No LLM-originated experiments yet. Run an analysis to generate one.</div>
      ) : (
        <table>
          <thead><tr><th>ID</th><th>Hypothesis</th><th>Origin</th><th>Status</th><th>Metrics</th></tr></thead>
          <tbody>
            {llmExps.map((e: Experiment) => (
              <tr key={e.experiment_id}>
                <td className="mono">{e.experiment_id}</td>
                <td>{e.hypothesis?.slice(0, 80)}</td>
                <td><span className={`pill ${e.origin === "llm" ? "pill-accent" : "pill-warning"}`}>{e.origin}</span></td>
                <td><span className={`pill ${PASSED_STATUSES.has(e.status) ? "pill-positive" : FAILED_STATUSES.has(e.status) ? "pill-negative" : "pill-accent"}`}>{e.status}</span></td>
                <td className="mono">{e.metrics ? JSON.stringify(e.metrics).slice(0, 40) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
