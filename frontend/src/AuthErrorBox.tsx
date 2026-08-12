import { Link } from "react-router-dom";

export function AuthErrorBox({ message }: { message?: string }) {
  return (
    <div className="error-box" style={{ borderColor: "var(--warning)" }}>
      <p style={{ color: "var(--warning)", fontWeight: 600 }}>Not connected</p>
      <p style={{ color: "var(--fg-muted)", marginTop: "var(--space-1)" }}>
        {message || "Set your API token to access this page."}
      </p>
      <Link to="/settings">
        <button style={{ marginTop: "var(--space-3)" }}>Go to Settings</button>
      </Link>
    </div>
  );
}

export function isAuthError(err: unknown): boolean {
  return err instanceof Error && err.name === "AuthError";
}
