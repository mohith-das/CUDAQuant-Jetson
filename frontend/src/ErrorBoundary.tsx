import { Component, type ReactNode } from "react";

interface Props { children: ReactNode; }
interface State { error: Error | null; }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: "var(--space-6)", color: "var(--negative)" }}>
          <h2>Something went wrong on this page</h2>
          <pre style={{ marginTop: "var(--space-4)", color: "var(--fg-muted)", fontSize: "var(--text-body)" }}>
            {this.state.error.message}
          </pre>
          <button
            onClick={() => this.setState({ error: null })}
            style={{ marginTop: "var(--space-4)" }}
          >
            Try Again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
