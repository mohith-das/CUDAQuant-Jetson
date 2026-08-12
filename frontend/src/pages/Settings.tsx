import { useState, useEffect } from "react";
import { getAuthToken, setAuthToken, clearAuthToken } from "../api";

export default function Settings() {
  const [tokenInput, setTokenInput] = useState(getAuthToken());
  const [tokenValid, setTokenValid] = useState<boolean | null>(null);

  const checkToken = async (tok: string) => {
    if (!tok) { setTokenValid(null); return; }
    try {
      const r = await fetch(`${window.location.origin}/api/system/`, {
        headers: { Authorization: `Bearer ${tok}` },
      });
      setTokenValid(r.status === 200);
    } catch { setTokenValid(false); }
  };

  useEffect(() => { checkToken(getAuthToken()); }, []);

  return (
    <div>
      <h2>Settings</h2>
      <div className="card" style={{ marginBottom: "var(--space-6)", borderColor: tokenValid === false ? "var(--negative)" : undefined }}>
        <h3>API Connection</h3>
        <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center", flexWrap: "wrap" }}>
          <input type="password" value={tokenInput} onChange={e => setTokenInput(e.target.value)} placeholder="API_AUTH_TOKEN" style={{ flex: 1, minWidth: 200 }} />
          <span className={`pill ${tokenValid === true ? "pill-positive" : tokenValid === false ? "pill-negative" : ""}`}>
            {tokenValid === true ? "Valid" : tokenValid === false ? "Invalid" : "—"}
          </span>
          <button onClick={() => setAuthToken(tokenInput)} disabled={!tokenInput.trim()}>Save</button>
          <button onClick={clearAuthToken} className="btn-danger" style={{ fontSize: "var(--text-eyebrow)" }}>Clear</button>
        </div>
        <p style={{ color: "var(--fg-faint)", fontSize: "var(--text-eyebrow)", marginTop: "var(--space-2)" }}>
          Token in localStorage. Paste from ~/code/cudaquant/.env API_AUTH_TOKEN.
        </p>
      </div>

      <div className="cards">
        <div className="card">
          <h3>MCP Server</h3>
          <p>Status: <span className="pill pill-positive">Available</span></p>
          <p className="mono">Tools: 19 (14 READ + 5 WRITE)</p>
          <pre style={{ fontSize: "var(--text-eyebrow)", background: "var(--surface-raised)", padding: "var(--space-3)" }}>
{`{
  "mcpServers": {
    "cudaquant": {
      "command": "python",
      "args": ["mcp_server/cudaquant_mcp.py"],
      "env": { "API_AUTH_TOKEN": "your-token", "PYTHONPATH": "." }
    }
  }
}`}
          </pre>
        </div>
        <div className="card">
          <h3>Telegram</h3>
          <p>Bot: <span className="pill pill-positive">Configured</span></p>
          <p style={{ color: "var(--fg-faint)", fontSize: "var(--text-eyebrow)" }}>
            Alerts on: kill switch, scheduler failure, challenger ready.
          </p>
        </div>
        <div className="card">
          <h3>Security</h3>
          <p>API auth: <span className="pill pill-positive">Enabled</span></p>
          <ul style={{ color: "var(--fg-muted)", paddingLeft: "var(--space-4)", marginTop: "var(--space-2)" }}>
            <li>TRADING_MODE / ENABLE_LIVE_TRADING — UI only</li>
            <li>SCHEDULER_AUTO_EXECUTE — UI only</li>
            <li>Kill switch disengage — UI only</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
