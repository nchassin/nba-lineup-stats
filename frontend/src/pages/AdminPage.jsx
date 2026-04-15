import { useState, useEffect, useRef } from "react";
import { api } from "../api";

export default function AdminPage() {
  const [status, setStatus] = useState(null);
  const [maxGames, setMaxGames] = useState("");
  const pollRef = useRef(null);

  function fetchStatus() {
    api.status().then(setStatus).catch(console.error);
  }

  useEffect(() => {
    fetchStatus();
    pollRef.current = setInterval(fetchStatus, 3000);
    return () => clearInterval(pollRef.current);
  }, []);

  async function startSync() {
    const mg = maxGames ? parseInt(maxGames) : null;
    await api.triggerSync(mg);
    fetchStatus();
  }

  const running = status?.running;

  return (
    <div className="page">
      <h1 className="page-title">Data Sync</h1>
      <p className="page-subtitle">
        Pull NBA game and lineup data from the official stats API for the 2025-26 season.
        The full sync fetches every game's play-by-play and reconstructs all 5-man lineups.
      </p>

      <div className="admin-card">
        <h2 className="admin-section">Sync Status</h2>
        <div className={`status-badge ${running ? "running" : "idle"}`}>
          {running ? "Running" : "Idle"}
        </div>
        <p className="status-message">{status?.message || "—"}</p>

        <div className="admin-controls">
          <div className="form-row">
            <label className="form-label">
              Max games to fetch (blank = all)
              <input
                type="number"
                className="form-input"
                placeholder="e.g. 5"
                value={maxGames}
                onChange={(e) => setMaxGames(e.target.value)}
                disabled={running}
              />
            </label>
          </div>
          <button
            className="btn-primary"
            onClick={startSync}
            disabled={running}
          >
            {running ? "Sync in Progress…" : "Start Sync"}
          </button>
        </div>
      </div>

      <div className="admin-card" style={{ marginTop: "1.5rem" }}>
        <h2 className="admin-section">How It Works</h2>
        <ol className="how-it-works">
          <li>
            <strong>Game Log</strong> — fetches all 2025-26 regular season games from <code>stats.nba.com</code>
          </li>
          <li>
            <strong>Play-by-Play</strong> — for each game, downloads the full event log and reconstructs
            which 5 players were on the court at every second
          </li>
          <li>
            <strong>Lineup Stats</strong> — pulls official per-lineup box scores (pts, reb, ast, +/-, etc.)
            from the NBA's lineup dashboard
          </li>
          <li>
            <strong>Database</strong> — saves everything locally so searches are instant
          </li>
        </ol>
        <p className="admin-note">
          Each game takes ~5 API calls with short delays to avoid rate limiting. Expect ~1 minute per 10 games.
        </p>
      </div>
    </div>
  );
}
