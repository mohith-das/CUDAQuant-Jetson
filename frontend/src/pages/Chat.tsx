import { useState } from "react";
import { apiFetch } from "../api";

interface Message { role: "user" | "assistant"; content: string; }
interface ToolCall { tool: string; result: unknown; error?: string; }

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [toolResults, setToolResults] = useState<ToolCall[]>([]);

  const send = async () => {
    if (!input.trim()) return;
    const userMsg: Message = { role: "user", content: input };
    const updated = [...messages, userMsg];
    setMessages(updated);
    setInput("");
    setLoading(true);
    setToolResults([]);

    try {
      const r = await apiFetch<{ content: string; tool_calls: ToolCall[]; budget_remaining: number }>(
        "/api/chat/",
        { method: "POST", body: JSON.stringify({ messages: updated }) },
      );
      setMessages([...updated, { role: "assistant", content: r.content || "(no response)" }]);
      if (r.tool_calls?.length) setToolResults(r.tool_calls);
    } catch (e: unknown) {
      setMessages([...updated, { role: "assistant", content: `Error: ${(e as Error).message}` }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 140px)" }}>
      <h2>AI Assistant</h2>
      <div style={{ flex: 1, overflow: "auto", background: "var(--surface)", borderRadius: 8, padding: "var(--space-4)", marginBottom: "var(--space-4)" }}>
        {messages.length === 0 && (
          <div className="empty-state" style={{ padding: "var(--space-8)" }}>
            Ask me about your strategies, experiments, models, or account.
            I can run backtests and check market regimes.
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} style={{ marginBottom: "var(--space-3)", padding: "var(--space-3)", borderRadius: 8,
            background: m.role === "user" ? "var(--surface-raised)" : "transparent",
            border: m.role === "user" ? "1px solid var(--border)" : "none",
          }}>
            <strong style={{ color: m.role === "user" ? "var(--accent)" : "var(--positive)", fontSize: "var(--text-eyebrow)" }}>
              {m.role === "user" ? "You" : "Assistant"}
            </strong>
            <pre style={{ whiteSpace: "pre-wrap", fontFamily: "var(--font-ui)", fontSize: "var(--text-body)", color: "var(--fg)", marginTop: "var(--space-1)" }}>
              {m.content}
            </pre>
          </div>
        ))}
        {loading && <div className="skeleton" style={{ height: 40 }} />}
      </div>
      {toolResults.length > 0 && (
        <div style={{ marginBottom: "var(--space-2)", fontSize: "var(--text-eyebrow)", color: "var(--fg-muted)" }}>
          Tool calls: {toolResults.map(t => t.tool).join(", ")}
        </div>
      )}
      <div style={{ display: "flex", gap: "var(--space-2)" }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Ask about your platform..."
          style={{ flex: 1 }}
          disabled={loading}
        />
        <button onClick={send} disabled={loading || !input.trim()}>
          {loading ? "..." : "Send"}
        </button>
      </div>
    </div>
  );
}
