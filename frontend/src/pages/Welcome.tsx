import { useState } from "react";
import { apiFetch } from "../api";
import { Link } from "react-router-dom";

export default function Welcome() {
  const [step, setStep] = useState(0);
  const [results, setResults] = useState<Record<string,string>>({});
  const [loading, setLoading] = useState(false);

  const runStep = async (label: string, fn: () => Promise<unknown>) => {
    setLoading(true);
    try {
      const r = await fn();
      setResults(prev => ({...prev, [label]: JSON.stringify(r).slice(0,200)}));
      setStep(s => s + 1);
    } catch (e: unknown) {
      setResults(prev => ({...prev, [label]: `Error: ${(e as Error).message}`}));
    }
    setLoading(false);
  };

  const steps = [
    {
      title: "Check System Health",
      action: () => runStep("health", () => apiFetch("/health")),
      done: !!results["health"],
    },
    {
      title: "Check Readiness",
      action: () => runStep("readiness", () => apiFetch("/readiness")),
      done: !!results["readiness"],
    },
    {
      title: "Generate Sample Data",
      action: () => runStep("data", () => apiFetch("/api/data/generate?symbols=AAPL&days=5&frequency=5m", {method:"POST"})),
      done: !!results["data"],
    },
    {
      title: "Run First Backtest",
      action: () => runStep("backtest", () => apiFetch("/api/backtests/run",{method:"POST",body:JSON.stringify({strategy:"intraday_momentum",params:{lookback:10},symbols:["AAPL"],days:7,frequency:"5m"})})),
      done: !!results["backtest"],
    },
    {
      title: "Create First Experiment",
      action: () => runStep("experiment", () => apiFetch("/api/experiments/propose",{method:"POST",body:JSON.stringify({hypothesis:"Initial strategy test",origin:"manual"})})),
      done: !!results["experiment"],
    },
  ];

  return (
    <div style={{maxWidth:640,margin:"var(--space-8) auto"}}>
      <h2>Welcome to CUDAQuant</h2>
      <p style={{color:"var(--fg-muted)",marginBottom:"var(--space-6)"}}>
        Let's get your quant research platform set up. Each step calls the real API.
      </p>
      {steps.map((s, i) => (
        <div key={i} className="card" style={{marginBottom:"var(--space-4)",opacity:i>step?0.5:1}}>
          <h3>{i+1}. {s.title}</h3>
          {results[s.title.toLowerCase().split(" ")[0]] ? (
            <p className="mono" style={{fontSize:"var(--text-eyebrow)",color:"var(--positive)",marginTop:"var(--space-2)"}}>
              {results[s.title.toLowerCase().split(" ")[0]]}
            </p>
          ) : i === step ? (
            <button onClick={s.action} disabled={loading} style={{marginTop:"var(--space-2)"}}>
              {loading ? "Running..." : `Run Step ${i+1}`}
            </button>
          ) : null}
        </div>
      ))}
      {step >= steps.length && (
        <div style={{textAlign:"center",marginTop:"var(--space-8)"}}>
          <p style={{fontSize:"var(--text-heading)",color:"var(--positive)",marginBottom:"var(--space-4)"}}>All set!</p>
          <div style={{display:"flex",gap:"var(--space-2)",justifyContent:"center",flexWrap:"wrap"}}>
            <Link to="/strategies"><button>Strategy Lab</button></Link>
            <Link to="/experiments"><button>Experiments</button></Link>
            <Link to="/data"><button>Data Explorer</button></Link>
            <Link to="/dashboard"><button>Dashboard</button></Link>
          </div>
        </div>
      )}
    </div>
  );
}
