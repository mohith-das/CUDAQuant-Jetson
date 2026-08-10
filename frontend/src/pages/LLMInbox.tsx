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

const PASSED_STATUSES = new Set([
  "backtest_passed",
  "paper_candidate",
  "paper_running",
  "probation",
  "production",
]);
const FAILED_STATUSES = new Set(["failed", "rejected"]);

const fmtTime = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleString() : "—";

export default function LLMInbox() {
  const { data: exps, isLoading } = useQuery({
    queryKey: ["experiments"],
    queryFn: () => apiFetch<Experiment[]>("/api/experiments/"),
    refetchInterval: 5000,
  });
  const { data: system } = useQuery({
    queryKey: ["system"],
    queryFn: () => apiFetch<Record<string, unknown>>("/api/system/"),
    refetchInterval: 10000,
  });
  const { data: scheduler } = useQuery({
    queryKey: ["scheduler"],
    queryFn: () => apiFetch<Record<string, unknown>>("/api/scheduler/"),
    refetchInterval: 5000,
  });
  const [msg, setMsg] = useState("");

  const llmExps = (exps ?? []).filter((e) => e.origin === "llm");
  const passed = llmExps.filter((e) => PASSED_STATUSES.has(e.status)).length;
  const failed = llmExps.filter((e) => FAILED_STATUSES.has(e.status)).length;
  const pending = llmExps.length - passed - failed;

  const runAnalysis = async () => {
    setMsg("");
    try {
      const r = await apiFetch<Record<string, unknown>>(
        "/api/scheduler/jobs/llm_analyze/run-now",
        { method: "POST" }
      );
      setMsg(`Analysis triggered: ${String(r.last_result ?? "")}`);
      queryClient.invalidateQueries({ queryKey: ["experiments"] });
      queryClient.invalidateQueries({ queryKey: ["scheduler"] });
    } catch (e: unknown) {
      setMsg(`Run failed: ${(e as Error).message}`);
    }
  };

  const llmJob = scheduler?.llm_analyze as Record<string, unknown> | undefined;

  const budgetKeys = [
    "daily_calls",
    "daily_cost_usd",
    "monthly_cost_usd",
    "daily_limit",
    "daily_budget_usd",
    "monthly_budget_usd",
  ];
  const budgetAvailable = !!system && budgetKeys.some((k) => k in system);

  if (isLoading) return <p>Loading experiments...</p>;

  return (
    <div>
      <h2>LLM Inbox</h2>
      <div className="cards">
        <div className="card">
          <h3>LLM Proposals</h3>
          <p>{llmExps.length} total from LLM origin</p>
          <p className="safe-text">{passed} passed</p>
          <p className="danger-text">{failed} failed</p>
          <p>{pending} pending</p>
        </div>
        <div className="card">
          <h3>LLM Budget</h3>
          {budgetAvailable ? (
            budgetKeys.map((k) => (
              <p key={k}>
                {k}: {String(system[k] ?? "—")}
              </p>
            ))
          ) : (
            <>
              <p>LLM budget counters are not exposed by /api/system/ yet.</p>
              <p>Mode: {String(system?.trading_mode ?? "—")}</p>
              <p>GPU: {system?.gpu_active ? "✓ Active" : "✗ Inactive"}</p>
            </>
          )}
        </div>
        <div className="card">
          <h3>LLM Analyze Job</h3>
          <p>Last run: {fmtTime(llmJob?.last_run as string | null)}</p>
          <p>Last result: {String(llmJob?.last_result ?? "—")}</p>
          <button onClick={runAnalysis} style={{ marginTop: 8 }}>
            Run Analysis Now
          </button>
        </div>
      </div>

      {msg && <p style={{ marginBottom: 8 }}>{msg}</p>}

      {llmExps.length > 0 ? (
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Hypothesis</th>
              <th>Status</th>
              <th>Metrics</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {llmExps.map((e) => (
              <tr key={e.experiment_id}>
                <td>{e.experiment_id}</td>
                <td>{e.hypothesis}</td>
                <td>{e.status}</td>
                <td>
                  {e.metrics && Object.keys(e.metrics).length > 0
                    ? JSON.stringify(e.metrics)
                    : "—"}
                </td>
                <td>{fmtTime(e.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p>No LLM-originated experiments yet. Run analysis to propose one.</p>
      )}
    </div>
  );
}
