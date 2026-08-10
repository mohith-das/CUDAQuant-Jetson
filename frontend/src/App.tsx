import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "./api";
import Dashboard from "./pages/Dashboard";
import DataExplorer from "./pages/DataExplorer";
import StrategyLab from "./pages/StrategyLab";
import Experiments from "./pages/Experiments";
import ModelRegistry from "./pages/ModelRegistry";
import Regimes from "./pages/Regimes";
import Execution from "./pages/Execution";
import Chat from "./pages/Chat";
import System from "./pages/System";
import Scheduler from "./pages/Scheduler";
import LLMInbox from "./pages/LLMInbox";
import ModelComparison from "./pages/ModelComparison";
import { ErrorBoundary } from "./ErrorBoundary";

const nav = [
  { to: "/", label: "Dashboard" },
  { to: "/data", label: "Data" },
  { to: "/strategies", label: "Strategy Lab" },
  { to: "/experiments", label: "Experiments" },
  { to: "/llm", label: "LLM Inbox" },
  { to: "/models", label: "Models" },
  { to: "/models/compare", label: "Model Compare" },
  { to: "/regimes", label: "Regimes" },
  { to: "/execution", label: "Execution" },
  { to: "/scheduler", label: "Scheduler" },
  { to: "/chat", label: "Chat" },
  { to: "/system", label: "System" },
];

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="app">
          <nav className="nav">
            <h1 className="logo">CUDAQuant</h1>
            <div className="nav-links">
              {nav.map((n) => (
                <NavLink key={n.to} to={n.to} end={n.to === "/" || n.to === "/models"}>
                  {n.label}
                </NavLink>
              ))}
            </div>
          </nav>
          <main className="main">
            <ErrorBoundary>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/data" element={<DataExplorer />} />
              <Route path="/strategies" element={<StrategyLab />} />
              <Route path="/experiments" element={<Experiments />} />
              <Route path="/llm" element={<LLMInbox />} />
              <Route path="/models" element={<ModelRegistry />} />
              <Route path="/models/compare" element={<ModelComparison />} />
              <Route path="/regimes" element={<Regimes />} />
              <Route path="/execution" element={<Execution />} />
              <Route path="/scheduler" element={<Scheduler />} />
              <Route path="/chat" element={<Chat />} />
              <Route path="/system" element={<System />} />
            </Routes>
            </ErrorBoundary>
          </main>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
