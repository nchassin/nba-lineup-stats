import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";

export default function GamesPage() {
  const [teams, setTeams] = useState([]);
  const [games, setGames] = useState([]);
  const [selectedTeam, setSelectedTeam] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    api.teams().then(setTeams).catch(console.error);
  }, []);

  useEffect(() => {
    setLoading(true);
    api
      .games(selectedTeam || null)
      .then(setGames)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [selectedTeam]);

  const fetched = games.filter((g) => g.data_fetched);
  const pending = games.filter((g) => !g.data_fetched);

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Games</h1>
        <select
          className="select"
          value={selectedTeam}
          onChange={(e) => setSelectedTeam(e.target.value)}
        >
          <option value="">All Teams</option>
          {teams.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
            </option>
          ))}
        </select>
      </div>

      {loading && <div className="loading">Loading…</div>}

      {!loading && games.length === 0 && (
        <div className="empty-state">
          <p>No games found. Go to <strong>Data Sync</strong> to pull the season data.</p>
        </div>
      )}

      {!loading && games.length > 0 && (
        <>
          {fetched.length > 0 && (
            <section>
              <h2 className="section-title">Games with Lineup Data ({fetched.length})</h2>
              <GameTable games={fetched} onSelect={(g) => navigate(`/games/${g.id}`)} />
            </section>
          )}
          {pending.length > 0 && (
            <section style={{ marginTop: "2rem" }}>
              <h2 className="section-title" style={{ color: "var(--muted)" }}>
                Pending Data Fetch ({pending.length})
              </h2>
              <GameTable games={pending} muted />
            </section>
          )}
        </>
      )}
    </div>
  );
}

function GameTable({ games, onSelect, muted }) {
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Matchup</th>
            <th>Score</th>
          </tr>
        </thead>
        <tbody>
          {games.map((g) => (
            <tr
              key={g.id}
              className={`table-row ${muted ? "muted" : "clickable"}`}
              onClick={() => !muted && onSelect && onSelect(g)}
            >
              <td className="date-cell">{formatDate(g.game_date)}</td>
              <td>
                {g.away_team?.abbreviation} @ {g.home_team?.abbreviation}
              </td>
              <td className="score-cell">
                {g.home_score != null && g.away_score != null
                  ? `${g.away_score}–${g.home_score}`
                  : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatDate(iso) {
  const d = new Date(iso + "T12:00:00");
  return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
}
