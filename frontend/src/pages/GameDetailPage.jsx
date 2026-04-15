import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api } from "../api";
import LineupTable from "../components/LineupTable";

export default function GameDetailPage() {
  const { gameId } = useParams();
  const navigate = useNavigate();
  const [lineups, setLineups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTeam, setActiveTeam] = useState(null);

  useEffect(() => {
    setLoading(true);
    api
      .gameLineups(gameId)
      .then((data) => {
        setLineups(data);
        if (data.length > 0 && !activeTeam) {
          setActiveTeam(data[0].team_id);
        }
      })
      .catch((e) => setError(e.response?.data?.detail || "Failed to load lineups"))
      .finally(() => setLoading(false));
  }, [gameId]);

  const gameInfo = lineups[0] || null;

  // Parse "GSW @ LAL" into { away: "GSW", home: "LAL" }
  const matchupParts = gameInfo ? gameInfo.matchup.split(" @ ") : ["?", "?"];
  const awayAbbr = matchupParts[0];
  const homeAbbr = matchupParts[1];

  // Build a map of team_id → abbrev using player_ids context from the API
  // The API also exposes team_id on each lineup row — we find which team is away/home
  // by cross-referencing player team assignments from the first lineup of each team.
  // Simpler: the lineups API includes player_ids for each lineup. We know from the
  // matchup which team is home/away. The home team's team_id is in the game record,
  // but we don't have that directly. Instead, use the fact that lineups are returned
  // home team first (sorted by game_id then team_id). We'll label both correctly
  // by letting the user see both abbreviations clearly.
  const teamIds = [...new Set(lineups.map((l) => l.team_id))];

  // Match team_ids to abbrevs: we have two team_ids and two abbrevs.
  // We can figure this out by checking which lineup has the home team_id.
  // The game lineups endpoint doesn't directly tell us home vs away per team_id,
  // but the matchup string in each row is always "AWAY @ HOME".
  // Both home and away lineups share the same matchup string.
  // We'll look at which team scored correctly by summing per-team lineups' pts and
  // comparing to home_score / away_score.
  let teamLabels = {};
  if (gameInfo && teamIds.length === 2) {
    const t0pts = lineups.filter(l => l.team_id === teamIds[0]).reduce((s, l) => s + (l.pts || 0), 0);
    const t1pts = lineups.filter(l => l.team_id === teamIds[1]).reduce((s, l) => s + (l.pts || 0), 0);
    // home_score vs away_score
    const homeScore = gameInfo.home_score;
    const awayScore = gameInfo.away_score;
    // The team whose pts sum is closer to homeScore is the home team
    const t0IsHome = Math.abs(t0pts - homeScore) < Math.abs(t0pts - awayScore);
    if (t0IsHome) {
      teamLabels[teamIds[0]] = homeAbbr;
      teamLabels[teamIds[1]] = awayAbbr;
    } else {
      teamLabels[teamIds[0]] = awayAbbr;
      teamLabels[teamIds[1]] = homeAbbr;
    }
  }

  const filtered = activeTeam ? lineups.filter((l) => l.team_id === activeTeam) : lineups;

  return (
    <div className="page">
      <button className="back-btn" onClick={() => navigate(-1)}>← Back</button>

      {gameInfo && (
        <div className="game-header">
          <h1 className="page-title">{gameInfo.matchup}</h1>
          <div className="game-score">
            {gameInfo.away_score != null
              ? `${gameInfo.away_score} – ${gameInfo.home_score}`
              : "Score unavailable"}
          </div>
          <div className="game-date">{formatDate(gameInfo.game_date)}</div>
        </div>
      )}

      {loading && <div className="loading">Loading lineup data…</div>}
      {error && <div className="error">{error}</div>}

      {!loading && !error && (
        <>
          <div className="team-tabs">
            {teamIds.map((tid) => (
              <button
                key={tid}
                className={`tab-btn ${activeTeam === tid ? "active" : ""}`}
                onClick={() => setActiveTeam(tid)}
              >
                {teamLabels[tid] || `Team ${tid}`}
              </button>
            ))}
          </div>

          <LineupTable lineups={filtered} />
        </>
      )}
    </div>
  );
}

function formatDate(iso) {
  const d = new Date(iso + "T12:00:00");
  return d.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" });
}
