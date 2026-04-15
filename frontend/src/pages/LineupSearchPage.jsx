import { useState, useEffect, useRef } from "react";
import { api } from "../api";
import LineupTable from "../components/LineupTable";

export default function LineupSearchPage() {
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const [selectedPlayers, setSelectedPlayers] = useState([]);
  const [results, setResults] = useState(null);
  const [totals, setTotals] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const debounceRef = useRef(null);

  // Autocomplete player search
  useEffect(() => {
    if (query.length < 2) {
      setSuggestions([]);
      return;
    }
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      api.searchPlayers(query).then(setSuggestions).catch(() => setSuggestions([]));
    }, 300);
  }, [query]);

  function addPlayer(player) {
    if (selectedPlayers.find((p) => p.id === player.id)) return;
    if (selectedPlayers.length >= 5) return;
    setSelectedPlayers((prev) => [...prev, player]);
    setQuery("");
    setSuggestions([]);
  }

  function removePlayer(id) {
    setSelectedPlayers((prev) => prev.filter((p) => p.id !== id));
    setResults(null);
    setTotals(null);
  }

  async function search() {
    if (selectedPlayers.length < 2) return;
    setLoading(true);
    setError(null);
    setResults(null);
    setTotals(null);
    try {
      const ids = selectedPlayers.map((p) => p.id);
      const [rows, tots] = await Promise.all([
        api.searchLineups(ids),
        api.lineupTotals(ids),
      ]);
      setResults(rows);
      setTotals(tots);
    } catch (e) {
      setError(e.response?.data?.detail || "Search failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <h1 className="page-title">Lineup Search</h1>
      <p className="page-subtitle">
        Select 2–5 players to find every game they shared the court together, with full stats.
      </p>

      <div className="search-box">
        <div className="selected-players">
          {selectedPlayers.map((p) => (
            <span key={p.id} className="player-chip">
              {p.name}
              <button className="chip-remove" onClick={() => removePlayer(p.id)}>×</button>
            </span>
          ))}
          {selectedPlayers.length < 5 && (
            <div className="autocomplete-wrap">
              <input
                className="player-input"
                placeholder="Search player name…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              {suggestions.length > 0 && (
                <ul className="suggestions">
                  {suggestions.map((s) => (
                    <li key={s.id} onClick={() => addPlayer(s)} className="suggestion-item">
                      {s.name}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
        <button
          className="btn-primary"
          disabled={selectedPlayers.length < 2 || loading}
          onClick={search}
        >
          {loading ? "Searching…" : "Search"}
        </button>
      </div>

      {error && <div className="error">{error}</div>}

      {totals && results && (
        <>
          <div className="totals-bar">
            <div className="totals-label">
              <strong>{selectedPlayers.map((p) => p.name.split(" ").pop()).join(" · ")}</strong>
              <span className="totals-games">{totals.games} game{totals.games !== 1 ? "s" : ""}</span>
            </div>
            <div className="totals-stats">
              <Stat label="MIN" value={totals.minutes} />
              <Stat label="+/-" value={fmtPM(totals.plus_minus)} />
              <Stat label="PTS" value={totals.pts} />
              <Stat label="REB" value={totals.reb} />
              <Stat label="AST" value={totals.ast} />
              <Stat label="FG%" value={totals.fg_pct != null ? `${totals.fg_pct}%` : "—"} />
              <Stat label="3P%" value={totals.fg3_pct != null ? `${totals.fg3_pct}%` : "—"} />
            </div>
          </div>

          {results.length === 0 ? (
            <div className="empty-state">No games found for this lineup combination.</div>
          ) : (
            <LineupTable lineups={results} showGame showDate />
          )}
        </>
      )}
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="total-stat">
      <div className="total-stat-label">{label}</div>
      <div className="total-stat-value">{value ?? "—"}</div>
    </div>
  );
}

function fmtPM(v) {
  if (v == null) return "—";
  return v > 0 ? `+${v}` : String(v);
}
