import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient, hasAuthToken, setAuthToken } from "./api";
import { useState } from "react";
import Dashboard from "./pages/Dashboard";
import DataExplorer from "./pages/DataExplorer";
import StrategyLab from "./pages/StrategyLab";
import Experiments from "./pages/Experiments";
import ModelRegistry from "./pages/ModelRegistry";
import Regimes from "./pages/Regimes";
import Execution from "./pages/Execution";
import Chat from "./pages/Chat";
import System from "./pages/System";
import Welcome from "./pages/Welcome";
import Settings from "./pages/Settings";
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
  { to: "/settings", label: "Settings" },
  { to: "/system", label: "System" },
];

export default function App() {
  const [tokenInput, setTokenInput] = useState("");

  if (!hasAuthToken()) {
    return (
      <QueryClientProvider client={queryClient}>
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "center",
          minHeight: "100vh", background: "var(--bg)", color: "var(--fg)",
          fontFamily: "var(--font-ui)", padding: "var(--space-4)",
        }}>
          <div style={{
            background: "var(--surface)", border: "1px solid var(--border)",
            borderRadius: 12, padding: "var(--space-8)", maxWidth: 480, width: "100%",
          }}>
            <h1 style={{ color: "var(--accent)", fontSize: "var(--text-title)", marginBottom: "var(--space-2)" }}>CUDAQuant</h1>
            <p style={{ color: "var(--fg-muted)", marginBottom: "var(--space-6)" }}>
              Connect to your Jetson instance. Paste the API token from your .env file
              or Infisical dev environment.
            </p>
            <input
              type="password"
              value={tokenInput}
              onChange={e => setTokenInput(e.target.value)}
              placeholder="Paste API_AUTH_TOKEN here..."
              style={{ width: "100%", marginBottom: "var(--space-3)", fontSize: "var(--text-body)" }}
            />
            <button
              onClick={() => { if (tokenInput.trim()) setAuthToken(tokenInput.trim()); }}
              disabled={!tokenInput.trim()}
              style={{ width: "100%" }}
            >
              Connect
            </button>
            <p style={{ color: "var(--fg-faint)", fontSize: "var(--text-eyebrow)", marginTop: "var(--space-4)" }}>
              Token is in ~/code/cudaquant/.env or Infisical. It stays in your browser&apos;s localStorage.
            </p>
          </div>
        </div>
      </QueryClientProvider>
    );
  }

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
              <Route path="/welcome" element={<Welcome />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/system" element={<System />} />
            </Routes>
            </ErrorBoundary>
          </main>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
