import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiFetch, queryClient } from "../api";

interface ModelInfo {
  model_id: string;
  family: string;
  version: number;
  status: string;
  metrics: Record<string, unknown> | null;
  created_at: string;
  parent_id?: string;
  origin?: string;
}

interface ExperimentInfo {
  experiment_id: string;
  hypothesis: string;
  status: string;
  origin: string;
}

const SECTION_LABELS: Record<string, string> = {
  champion: "Champion",
  challenger: "Challengers",
  candidate: "Candidates",
  retired: "Retired",
};

const fmtMetrics = (metrics: Record<string, unknown> | null | undefined) => {
  if (!metrics) return "—";
  const entries = Object.entries(metrics);
  if (entries.length === 0) return "—";
  return entries
    .map(([k, v]) => `${k}=${typeof v === "number" ? v.toFixed(4) : String(v ?? "")}`)
    .join(", ");
};

function MetricsTable({ metrics }: { metrics: Record<string, unknown> | null | undefined }) {
  const entries = metrics ? Object.entries(metrics) : [];
  if (entries.length === 0) return <p>No metrics recorded.</p>;
  return (
    <table>
      <tbody>
        {entries.map(([k, v]) => (
          <tr key={k}>
            <td>{k}</td>
            <td>{typeof v === "number" ? v.toFixed(4) : String(v ?? "")}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function ModelComparison() {
  const { data: models, isLoading } = useQuery({
    queryKey: ["models"],
    queryFn: () => apiFetch<ModelInfo[]>("/api/models/"),
    refetchInterval: 10000,
  });
  const { data: scheduler } = useQuery({
    queryKey: ["scheduler"],
    queryFn: () => apiFetch<Record<string, unknown>>("/api/scheduler/"),
    refetchInterval: 10000,
  });
  const { data: exps } = useQuery({
    queryKey: ["experiments"],
    queryFn: () => apiFetch<ExperimentInfo[]>("/api/experiments/"),
    refetchInterval: 30000,
  });

  const [promoteTarget, setPromoteTarget] = useState<ModelInfo | null>(null);
  const [enableConfirm, setEnableConfirm] = useState("");
  const [livePerf, setLivePerf] = useState<Record<string, Record<string, unknown>>>({});
  const [msg, setMsg] = useState("");

  const autoExec = Boolean(scheduler?.auto_execute_enabled);

  const byStatus = useMemo(() => {
    const groups: Record<string, ModelInfo[]> = {
      champion: [],
      challenger: [],
      candidate: [],
      retired: [],
    };
    (models ?? []).forEach((m) => {
      if (!groups[m.status]) groups[m.status] = [];
      groups[m.status].push(m);
    });
    return groups;
  }, [models]);

  const parentExps = useMemo(() => {
    const map = new Map<string, { hypothesis: string; origin: string }>();
    (exps ?? []).forEach((e) => {
      map.set(e.experiment_id, {
        hypothesis: e.hypothesis,
        origin: e.origin,
      });
    });
    return map;
  }, [exps]);

  const originCell = (m: ModelInfo) => {
    const pe = m.parent_id ? parentExps.get(m.parent_id) : undefined;
    if (pe) return <span title={pe.hypothesis}>{pe.origin} exp {m.parent_id}</span>;
    return <span>—</span>;
  };

  const fetchLivePerformance = async (modelId: string) => {
    setMsg("");
    try {
      const data = await apiFetch<Record<string, unknown>>(
        `/api/models/${modelId}/live-performance`
      );
      setLivePerf((prev) => ({ ...prev, [modelId]: data }));
    } catch (e: unknown) {
      setMsg(`Live performance failed: ${(e as Error).message}`);
    }
  };

  const confirmPromote = async () => {
    if (!promoteTarget) return;
    setMsg("");
    try {
      const r = await apiFetch<Record<string, unknown>>(
        `/api/models/${promoteTarget.model_id}/promote`,
        { method: "POST" }
      );
      setMsg(`${promoteTarget.model_id} is now ${String(r.status ?? "")}`);
      setPromoteTarget(null);
      queryClient.invalidateQueries({ queryKey: ["models"] });
    } catch (e: unknown) {
      setMsg(`Promotion failed: ${(e as Error).message}`);
    }
  };

  const enableLiveExecution = async () => {
    setMsg("");
    if (enableConfirm !== "ENABLE") return;
    try {
      await apiFetch("/api/scheduler/auto-execute", {
        method: "PUT",
        body: JSON.stringify({ confirm: "ENABLE" }),
      });
      setEnableConfirm("");
      queryClient.invalidateQueries({ queryKey: ["scheduler"] });
    } catch (e: unknown) {
      setMsg(`Enable failed: ${(e as Error).message}`);
    }
  };

  if (isLoading) return <p>Loading models...</p>;

  return (
    <div>
      <h2>Champion vs Challenger</h2>

      <div className={`card ${autoExec ? "danger" : ""}`} style={{ marginTop: 16 }}>
        <h3>Live Execution</h3>
        <p className={autoExec ? "danger-text" : "safe-text"}>
          {autoExec ? "⚠ AUTO-EXECUTE ENABLED" : "✓ Auto-execute disabled"}
        </p>
        {autoExec ? (
          <p>Already enabled — disable it from the Scheduler page.</p>
        ) : (
          <div style={{ marginTop: 8 }}>
            <input
              type="text"
              placeholder='Type "ENABLE" to confirm'
              value={enableConfirm}
              onChange={(e) => setEnableConfirm(e.target.value)}
            />
            <button
              onClick={enableLiveExecution}
              disabled={enableConfirm !== "ENABLE"}
            >
              Enable Live Execution
            </button>
          </div>
        )}
      </div>

      {byStatus.champion.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <h3>{SECTION_LABELS.champion}</h3>
          <div className="cards">
            {byStatus.champion.map((m) => (
              <div className="card" key={m.model_id}>
                <h3>{m.family} v{m.version}</h3>
                <p>{m.model_id}</p>
                <p>Promoted: {m.created_at}</p>
                <MetricsTable metrics={m.metrics} />
                <button
                  onClick={() => fetchLivePerformance(m.model_id)}
                  style={{ marginTop: 8 }}
                >
                  Live Performance
                </button>
                {livePerf[m.model_id] && (
                  <div style={{ marginTop: 8 }}>
                    <p>Filled orders: {String(livePerf[m.model_id].filled_orders ?? "—")}</p>
                    <p>
                      Sharpe (backtest):{" "}
                      {livePerf[m.model_id].backtest_sharpe != null
                        ? Number(livePerf[m.model_id].backtest_sharpe).toFixed(4)
                        : "—"}
                    </p>
                    <p>
                      Max drawdown (backtest):{" "}
                      {livePerf[m.model_id].backtest_max_drawdown != null
                        ? Number(livePerf[m.model_id].backtest_max_drawdown).toFixed(4)
                        : "—"}
                    </p>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {(["challenger", "candidate", "retired"] as const).map((st) => {
        const list = byStatus[st];
        if (!list || list.length === 0) return null;
        return (
          <div key={st} style={{ marginTop: 16 }}>
            <h3>{SECTION_LABELS[st]}</h3>
            <table>
              <thead>
                <tr>
                  <th>Model</th>
                  <th>Family</th>
                  <th>Version</th>
                  <th>Metrics</th>
                  <th>Origin</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {list.map((m) => (
                  <tr key={m.model_id}>
                    <td>{m.model_id}</td>
                    <td>{m.family}</td>
                    <td>{m.version}</td>
                    <td>{fmtMetrics(m.metrics)}</td>
                    <td>{originCell(m)}</td>
                    <td>
                      {st === "challenger" && (
                        <button onClick={() => setPromoteTarget(m)}>
                          Promote to Champion
                        </button>
                      )}
                      {st === "candidate" && (
                        <button onClick={() => setPromoteTarget(m)}>
                          Promote to Challenger
                        </button>
                      )}
                      {st === "retired" && "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })}

      {byStatus.challenger.length > 0 && (
        <p style={{ marginTop: 12, fontSize: 12, color: "#8b949e" }}>
          Note: model parent/origin linkage is not exposed by the model API yet,
          so "Origin" shows "—" unless a parent experiment can be matched.
        </p>
      )}

      {msg && <p style={{ marginTop: 12 }}>{msg}</p>}

      {promoteTarget && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 10,
          }}
        >
          <div className="card" style={{ width: 420 }}>
            <h3>Confirm Promotion</h3>
            <p>
              Promote <strong>{promoteTarget.model_id}</strong> (
              {promoteTarget.family} v{promoteTarget.version}) to{" "}
              {promoteTarget.status === "candidate" ? "challenger" : "champion"}?
            </p>
            {promoteTarget.status === "challenger" && (
              <p className="danger-text">
                This retires the current champion in this family.
              </p>
            )}
            <div style={{ marginTop: 12 }}>
              <button onClick={confirmPromote}>Confirm Promote</button>
              <button
                onClick={() => setPromoteTarget(null)}
                className="btn-danger"
                style={{ marginLeft: 8 }}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
