import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiFetch, queryClient } from "../api";
import { AuthErrorBox, isAuthError } from "../AuthErrorBox";

interface SearchResult { symbol: string; name: string; exchange: string; type: string; }
interface Quote {
  price: number | null; change: number | null; changePercent: number | null;
  prevClose: number | null; open: number | null; high: number | null;
  low: number | null; volume: number | null;
}
interface SymbolInfo {
  symbol: string;
  quote: Quote | null;
  profile: Record<string, unknown>;
  news: Array<Record<string, unknown>>;
}
interface Universe { id: string; name: string; symbols: string[]; }

const fmtNum = (v: number | null | undefined, digits = 2): string =>
  v === null || v === undefined ? "—" : Number(v).toFixed(digits);
const fmtVol = (v: number | null | undefined): string =>
  v === null || v === undefined ? "—" : Number(v).toLocaleString("en-US");

export default function Market() {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const [searchError, setSearchError] = useState<Error | null>(null);

  const [selected, setSelected] = useState<SymbolInfo | null>(null);
  const [loadingInfo, setLoadingInfo] = useState(false);
  const [infoError, setInfoError] = useState<Error | null>(null);

  const [universeId, setUniverseId] = useState("");
  const [newName, setNewName] = useState("");
  const [mutating, setMutating] = useState(false);
  const [actionError, setActionError] = useState<Error | null>(null);

  const { data: universes, isLoading: universesLoading, error: universesError } = useQuery({
    queryKey: ["universes"],
    queryFn: () => apiFetch<Universe[]>("/api/universe/"),
  });

  if (isAuthError(searchError) || isAuthError(infoError) || isAuthError(universesError) || isAuthError(actionError)) {
    return <AuthErrorBox />;
  }

  const runSearch = async () => {
    const term = q.trim();
    if (!term) return;
    setSearching(true);
    setSearchError(null);
    setSearched(true);
    try {
      const data = await apiFetch<{ results: SearchResult[] }>(
        `/api/data/search?q=${encodeURIComponent(term)}&limit=10`
      );
      setResults(data.results ?? []);
    } catch (e: unknown) {
      setSearchError(e as Error);
      setResults([]);
    } finally {
      setSearching(false);
    }
  };

  const selectSymbol = async (symbol: string) => {
    setLoadingInfo(true);
    setInfoError(null);
    try {
      const info = await apiFetch<SymbolInfo>(`/api/data/${encodeURIComponent(symbol)}/info`);
      setSelected(info);
    } catch (e: unknown) {
      setInfoError(e as Error);
      setSelected(null);
    } finally {
      setLoadingInfo(false);
    }
  };

  const createUniverse = async () => {
    const name = newName.trim();
    if (!name) return;
    setMutating(true);
    setActionError(null);
    try {
      const created = await apiFetch<Universe>("/api/universe/", {
        method: "POST",
        body: JSON.stringify({ name, symbols: [] }),
      });
      setNewName("");
      setUniverseId(created.id);
      await queryClient.invalidateQueries({ queryKey: ["universes"] });
    } catch (e: unknown) {
      setActionError(e as Error);
    } finally {
      setMutating(false);
    }
  };

  const addToUniverse = async () => {
    if (!universeId || !selected?.symbol) return;
    setMutating(true);
    setActionError(null);
    try {
      await apiFetch<Universe>(`/api/universe/${encodeURIComponent(universeId)}/symbols`, {
        method: "POST",
        body: JSON.stringify({ symbols: [selected.symbol] }),
      });
      await queryClient.invalidateQueries({ queryKey: ["universes"] });
    } catch (e: unknown) {
      setActionError(e as Error);
    } finally {
      setMutating(false);
    }
  };

  const activeUniverse = universes?.find((u) => u.id === universeId) ?? null;
  const quote = selected?.quote ?? null;
  const change = quote?.change ?? 0;
  const up = change >= 0;
  const hasProfile = selected ? Object.keys(selected.profile).length > 0 : false;
  const news = (selected?.news ?? []).slice(0, 5);

  return (
    <div>
      <h2>Market</h2>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) 320px", gap: "var(--space-6)", alignItems: "start" }}>
        <div>
          <form
            onSubmit={(e) => { e.preventDefault(); runSearch(); }}
            style={{ display: "flex", gap: "var(--space-2)", marginBottom: "var(--space-4)" }}
          >
            <input
              type="text"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search symbols or companies…"
              style={{ flex: 1 }}
            />
            <button type="submit" disabled={!q.trim() || searching}>
              {searching ? "Searching…" : "Search"}
            </button>
          </form>

          {searchError && <div className="error-box">Search failed: {searchError.message}</div>}
          {searching && <div className="skeleton" style={{ height: 120 }} />}
          {!searching && searched && !searchError && results.length === 0 && (
            <div className="empty-state">No matches for &quot;{q.trim()}&quot;</div>
          )}
          {!searching && results.length > 0 && (
            <table style={{ marginBottom: "var(--space-6)" }}>
              <thead>
                <tr><th>Symbol</th><th>Name</th><th>Exchange</th><th>Type</th><th>+</th></tr>
              </thead>
              <tbody>
                {results.map((r, i) => (
                  <tr key={`${r.symbol}-${i}`} onClick={() => selectSymbol(r.symbol)} style={{ cursor: "pointer" }}>
                    <td className="mono">{r.symbol}</td>
                    <td>{r.name}</td>
                    <td>{r.exchange}</td>
                    <td>{r.type}</td>
                    <td>
                      <button
                        onClick={(e) => { e.stopPropagation(); selectSymbol(r.symbol); }}
                        title={`Inspect ${r.symbol}`}
                        style={{ padding: "2px 10px" }}
                      >+</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {infoError && <div className="error-box">Info failed: {infoError.message}</div>}
          {loadingInfo && <div className="skeleton" style={{ height: 200 }} />}
          {!loadingInfo && selected && (
            <div className="cards">
              <div className="card">
                <h3>Quote — {selected.symbol}</h3>
                {quote ? (
                  <>
                    <div className="mono" style={{ fontSize: "var(--text-metric)", marginBottom: "var(--space-2)" }}>
                      {fmtNum(quote.price)}
                    </div>
                    <div className={up ? "positive" : "negative"} style={{ marginBottom: "var(--space-4)" }}>
                      {up ? "▲" : "▼"} {fmtNum(quote.change)} ({fmtNum(quote.changePercent)}%)
                    </div>
                    <table>
                      <tbody>
                        <tr><td style={{ color: "var(--fg-muted)" }}>Open</td><td className="mono">{fmtNum(quote.open)}</td></tr>
                        <tr><td style={{ color: "var(--fg-muted)" }}>High</td><td className="mono">{fmtNum(quote.high)}</td></tr>
                        <tr><td style={{ color: "var(--fg-muted)" }}>Low</td><td className="mono">{fmtNum(quote.low)}</td></tr>
                        <tr><td style={{ color: "var(--fg-muted)" }}>Prev Close</td><td className="mono">{fmtNum(quote.prevClose)}</td></tr>
                        <tr><td style={{ color: "var(--fg-muted)" }}>Volume</td><td className="mono">{fmtVol(quote.volume)}</td></tr>
                      </tbody>
                    </table>
                  </>
                ) : (
                  <p style={{ color: "var(--fg-muted)" }}>No quote data</p>
                )}
              </div>

              <div className="card">
                <h3>Profile</h3>
                {hasProfile ? (
                  <>
                    <p style={{ fontWeight: 600 }}>
                      {String(selected.profile.companyName ?? selected.symbol)}
                    </p>
                    <p style={{ color: "var(--fg-muted)", marginBottom: "var(--space-2)" }}>
                      {[selected.profile.sector, selected.profile.industry].filter(Boolean).join(" · ")}
                    </p>
                    <p>{String(selected.profile.description ?? "")}</p>
                  </>
                ) : (
                  <p style={{ color: "var(--fg-muted)" }}>No profile data</p>
                )}
              </div>

              <div className="card">
                <h3>News</h3>
                {news.length > 0 ? (
                  <ul style={{ listStyle: "none", paddingLeft: 0 }}>
                    {news.map((n, i) => {
                      const title = String(n.headline ?? n.title ?? "");
                      const url = String(n.url ?? "");
                      if (!title && !url) return null;
                      return (
                        <li key={i} style={{ marginBottom: "var(--space-2)" }}>
                          {url ? (
                            <a href={url} target="_blank" rel="noreferrer" style={{ color: "var(--accent)" }}>
                              {title || url}
                            </a>
                          ) : (
                            <span>{title || url}</span>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                ) : (
                  <p style={{ color: "var(--fg-muted)" }}>No recent news</p>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="card">
          <h3>Universes</h3>
          {universesLoading ? (
            <div className="skeleton" style={{ height: 120 }} />
          ) : universesError ? (
            <div className="error-box">Universe list failed: {universesError.message}</div>
          ) : (
            <>
              <select
                value={universeId}
                onChange={(e) => setUniverseId(e.target.value)}
                style={{ width: "100%", marginBottom: "var(--space-3)" }}
              >
                <option value="">— select universe —</option>
                {(universes ?? []).map((u) => (
                  <option key={u.id} value={u.id}>{u.name || "unnamed"}</option>
                ))}
              </select>

              {activeUniverse ? (
                <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-2)", marginBottom: "var(--space-4)" }}>
                  {activeUniverse.symbols.length > 0 ? (
                    activeUniverse.symbols.map((s) => (
                      <span key={s} className="pill pill-accent mono">{s}</span>
                    ))
                  ) : (
                    <p style={{ color: "var(--fg-muted)" }}>No symbols yet</p>
                  )}
                </div>
              ) : (
                <div className="empty-state" style={{ padding: "var(--space-4)" }}>
                  Select or create a universe
                </div>
              )}

              <form
                onSubmit={(e) => { e.preventDefault(); createUniverse(); }}
                style={{ display: "flex", gap: "var(--space-2)", marginBottom: "var(--space-3)" }}
              >
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="New universe name"
                  style={{ flex: 1 }}
                />
                <button type="submit" disabled={!newName.trim() || mutating}>Create</button>
              </form>

              <button
                onClick={addToUniverse}
                disabled={!universeId || !selected?.symbol || mutating}
                style={{ width: "100%" }}
              >
                {selected ? `Add ${selected.symbol} to universe` : "Add selected symbol to universe"}
              </button>

              {actionError && (
                <div className="error-box" style={{ marginTop: "var(--space-3)" }}>
                  Failed: {actionError.message}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
