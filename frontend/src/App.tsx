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
import System from "./pages/System";
import "./App.css";

const nav = [
  { to: "/", label: "Dashboard" },
  { to: "/data", label: "Data" },
  { to: "/strategies", label: "Strategy Lab" },
  { to: "/experiments", label: "Experiments" },
  { to: "/models", label: "Models" },
  { to: "/regimes", label: "Regimes" },
  { to: "/execution", label: "Execution" },
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
                <NavLink key={n.to} to={n.to} end={n.to === "/"}>
                  {n.label}
                </NavLink>
              ))}
            </div>
          </nav>
          <main className="main">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/data" element={<DataExplorer />} />
              <Route path="/strategies" element={<StrategyLab />} />
              <Route path="/experiments" element={<Experiments />} />
              <Route path="/models" element={<ModelRegistry />} />
              <Route path="/regimes" element={<Regimes />} />
              <Route path="/execution" element={<Execution />} />
              <Route path="/system" element={<System />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
