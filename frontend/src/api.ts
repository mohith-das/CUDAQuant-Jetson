import { QueryClient } from "@tanstack/react-query";

const API_BASE = window.location.origin;

export function getAuthToken(): string {
  return localStorage.getItem("api_auth_token") || "";
}

export async function apiFetch<T = unknown>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getAuthToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (res.status === 401) {
    throw new AuthError("Authentication required — set your API token in Settings");
  }
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

export class AuthError extends Error {
  constructor(msg: string) { super(msg); this.name = "AuthError"; }
}

export function setAuthToken(token: string) {
  localStorage.setItem("api_auth_token", token);
  window.location.reload();
}

export function clearAuthToken() {
  localStorage.removeItem("api_auth_token");
  window.location.reload();
}

export function hasAuthToken(): boolean {
  return !!getAuthToken();
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: { refetchOnWindowFocus: false, retry: 1 },
  },
});
