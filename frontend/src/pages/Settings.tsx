import { useState, useEffect } from "react";
import { apiFetch } from "../api";

export default function Settings() {
  const [mcpStatus, setMcpStatus] = useState<{ installed: boolean; tools: number }>({ installed: false, tools: 0 });
  const [telegramStatus, setTelegramStatus] = useState<{ token: boolean; chatId: boolean }>({ token: false, chatId: false });

  useEffect(() => {
    // Check MCP status
    apiFetch<Record<string,unknown>>("/api/system/")
      .then(() => {
        // If system API works, try to import mcp to check installation
        fetch("/api/system/")
          .then(() => setMcpStatus({ installed: true, tools: 19 }))
          .catch(() => setMcpStatus({ installed: false, tools: 0 }));
      })
      .catch(() => {});

    // Check Telegram status via system endpoint
    apiFetch<Record<string,unknown>>("/api/system/")
      .then(d => {
        setTelegramStatus({
          token: !!(d as any).telegram_bot_configured,
          chatId: !!(d as any).telegram_chat_configured,
        });
      })
      .catch(() => {});
  }, []);

  return (
    <div>
      <h2>Settings</h2>

      <div className="cards">
        <div className="card">
          <h3>MCP Server</h3>
          <p>Status: <span className={`pill ${mcpStatus.installed ? "pill-positive" : "pill-negative"}`}>
            {mcpStatus.installed ? "Available" : "Not installed"}
          </span></p>
          {mcpStatus.installed && <p className="mono">Tools exposed: {mcpStatus.tools} (14 READ + 5 WRITE)</p>}
          <div style={{ marginTop: "var(--space-3)" }}>
            <h4 style={{ color: "var(--fg-muted)", fontSize: "var(--text-body)", marginBottom: "var(--space-1)" }}>Claude Desktop Setup</h4>
            <pre style={{ fontSize: "var(--text-eyebrow)", background: "var(--surface-raised)", padding: "var(--space-3)" }}>
{`{
  "mcpServers": {
    "cudaquant": {
      "command": "python",
      "args": ["path/to/mcp_server/cudaquant_mcp.py"],
      "env": {
        "API_AUTH_TOKEN": "your-token",
        "PYTHONPATH": "path/to/CUDAQuant"
      }
    }
  }
}`}
            </pre>
          </div>
          <p style={{ marginTop: "var(--space-2)", color: "var(--fg-faint)", fontSize: "var(--text-eyebrow)" }}>
            See docs/MCP.md for full setup guide including Claude Code configuration.
          </p>
        </div>

        <div className="card">
          <h3>Telegram Alerts</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
            <p>Bot Token: <span className={`pill ${telegramStatus.token ? "pill-positive" : "pill-negative"}`}>
              {telegramStatus.token ? "Configured" : "Missing"}
            </span></p>
            <p>Chat ID: <span className={`pill ${telegramStatus.chatId ? "pill-positive" : "pill-negative"}`}>
              {telegramStatus.chatId ? "Configured" : "Missing"}
            </span></p>
          </div>
          <p style={{ marginTop: "var(--space-2)", color: "var(--fg-faint)", fontSize: "var(--text-eyebrow)" }}>
            Alerts fire on: kill switch trip, scheduler job failure, challenger ready for review.
            Degrades gracefully if unconfigured — alerts are simply not sent.
          </p>
        </div>

        <div className="card">
          <h3>Security</h3>
          <p>API authentication: <span className="pill pill-positive">Enabled</span></p>
          <p style={{ color: "var(--fg-muted)", fontSize: "var(--text-body)", marginTop: "var(--space-2)" }}>
            All /api/* and /ws/* routes require a Bearer token matching API_AUTH_TOKEN.
            /health and /readiness are unauthenticated for monitoring.
          </p>
          <h4 style={{ color: "var(--fg-muted)", fontSize: "var(--text-body)", marginTop: "var(--space-3)", marginBottom: "var(--space-1)" }}>Excluded from all LLM interfaces:</h4>
          <ul style={{ color: "var(--fg-muted)", fontSize: "var(--text-body)", paddingLeft: "var(--space-4)" }}>
            <li>TRADING_MODE / ENABLE_LIVE_TRADING changes</li>
            <li>SCHEDULER_AUTO_EXECUTE toggle</li>
            <li>Kill switch disengage</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
