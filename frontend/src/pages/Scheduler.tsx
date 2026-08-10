import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiFetch, queryClient } from "../api";

interface SchedulerJob {
  name: string;
  enabled: boolean;
  interval_seconds: number;
  last_run: string | null;
  last_result: string | null;
  next_run: string | null;
}

interface SchedulerState {
  ingest: SchedulerJob;
  retrain: SchedulerJob;
  evaluate: SchedulerJob;
  llm_analyze: SchedulerJob;
  auto_execute_enabled: boolean;
}

const JOB_NAMES = ["ingest", "retrain", "evaluate", "llm_analyze"] as const;

const fmtTime = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleString() : "—";

export default function Scheduler() {
  const { data: state, isLoading } = useQuery({
    queryKey: ["scheduler"],
    queryFn: () => apiFetch<SchedulerState>("/api/scheduler/"),
    refetchInterval: 5000,
  });
  const [confirm, setConfirm] = useState("");
  const [msg, setMsg] = useState("");
  const [intervals, setIntervals] = useState<Record<string, string>>({});

  const toggleJob = async (name: string, enabled: boolean) => {
    setMsg("");
    try {
      await apiFetch(`/api/scheduler/jobs/${name}`, {
        method: "PUT",
        body: JSON.stringify({ enabled }),
      });
      queryClient.invalidateQueries({ queryKey: ["scheduler"] });
    } catch (e: unknown) {
      setMsg(`Toggle failed: ${(e as Error).message}`);
    }
  };

  const saveInterval = async (name: string) => {
    setMsg("");
    const seconds = Number(intervals[name]);
    if (!Number.isFinite(seconds) || seconds <= 0) return;
    try {
      await apiFetch(`/api/scheduler/jobs/${name}`, {
        method: "PUT",
        body: JSON.stringify({ interval_seconds: seconds }),
      });
      queryClient.invalidateQueries({ queryKey: ["scheduler"] });
    } catch (e: unknown) {
      setMsg(`Interval update failed: ${(e as Error).message}`);
    }
  };

  const runNow = async (name: string) => {
    setMsg("");
    try {
      const r = await apiFetch<Record<string, unknown>>(
        `/api/scheduler/jobs/${name}/run-now`,
        { method: "POST" }
      );
      setMsg(`Run ${name}: ${String(r.last_result ?? "")}`);
      queryClient.invalidateQueries({ queryKey: ["scheduler"] });
    } catch (e: unknown) {
      setMsg(`Run failed: ${(e as Error).message}`);
    }
  };

  const enableAutoExecute = async () => {
    setMsg("");
    if (confirm !== "ENABLE") return;
    try {
      await apiFetch("/api/scheduler/auto-execute", {
        method: "PUT",
        body: JSON.stringify({ confirm: "ENABLE" }),
      });
      setConfirm("");
      queryClient.invalidateQueries({ queryKey: ["scheduler"] });
    } catch (e: unknown) {
      setMsg(`Enable failed: ${(e as Error).message}`);
    }
  };

  const disableAutoExecute = async () => {
    setMsg("");
    try {
      await apiFetch("/api/scheduler/auto-execute", { method: "DELETE" });
      queryClient.invalidateQueries({ queryKey: ["scheduler"] });
    } catch (e: unknown) {
      setMsg(`Disable failed: ${(e as Error).message}`);
    }
  };

  if (isLoading) return <p>Loading scheduler...</p>;
  if (!state) return <p>No scheduler state.</p>;

  return (
    <div>
      <h2>Scheduler</h2>
      <div className="cards">
        {JOB_NAMES.map((name) => {
          const job = state[name];
          if (!job) return null;
          return (
            <div className="card" key={name}>
              <h3>{job.name}</h3>
              <p>
                Status:{" "}
                <span className={job.enabled ? "safe-text" : "danger-text"}>
                  {job.enabled ? "Enabled" : "Disabled"}
                </span>
              </p>
              <p>Interval: every {job.interval_seconds}s</p>
              <p>Last run: {fmtTime(job.last_run)}</p>
              <p>Next run: {fmtTime(job.next_run)}</p>
              <p>Last result: {job.last_result ?? "—"}</p>
              <div style={{ marginTop: 8 }}>
                <button onClick={() => toggleJob(name, !job.enabled)}>
                  {job.enabled ? "Disable" : "Enable"}
                </button>
                <button onClick={() => runNow(name)} style={{ marginLeft: 8 }}>
                  Run Now
                </button>
              </div>
              <div style={{ marginTop: 8 }}>
                <input
                  type="number"
                  min={1}
                  style={{ width: 90 }}
                  value={intervals[name] ?? String(job.interval_seconds)}
                  onChange={(e) =>
                    setIntervals({ ...intervals, [name]: e.target.value })
                  }
                />
                <button onClick={() => saveInterval(name)}>
                  Set Interval (s)
                </button>
              </div>
            </div>
          );
        })}
      </div>

      <div
        className={`card ${state.auto_execute_enabled ? "danger" : ""}`}
        style={{ marginTop: 16 }}
      >
        <h3>Auto-Execute</h3>
        <p className={state.auto_execute_enabled ? "danger-text" : "safe-text"}>
          {state.auto_execute_enabled
            ? "⚠ AUTO-EXECUTE ENABLED"
            : "✓ Auto-execute disabled"}
        </p>
        <p>
          When enabled, the system may autonomously place orders after all
          risk gates pass.
        </p>
        {!state.auto_execute_enabled && (
          <div style={{ marginTop: 8 }}>
            <input
              type="text"
              placeholder='Type "ENABLE" to confirm'
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
            />
            <button
              onClick={enableAutoExecute}
              disabled={confirm !== "ENABLE"}
            >
              Enable Auto-Execute
            </button>
          </div>
        )}
        {state.auto_execute_enabled && (
          <button
            onClick={disableAutoExecute}
            className="btn-danger"
            style={{ marginTop: 8 }}
          >
            Disable Auto-Execute
          </button>
        )}
      </div>

      {msg && <p style={{ marginTop: 12 }}>{msg}</p>}
    </div>
  );
}
