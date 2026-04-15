import { useNavigate } from "react-router-dom";

const COLS = [
  { key: "minutes", label: "MIN", title: "Minutes on court" },
  { key: "plus_minus", label: "+/-", title: "Plus/Minus", fmt: fmtPM },
  { key: "pts", label: "PTS", title: "Points" },
  { key: "reb", label: "REB", title: "Rebounds" },
  { key: "ast", label: "AST", title: "Assists" },
  { key: "stl", label: "STL", title: "Steals" },
  { key: "blk", label: "BLK", title: "Blocks" },
  { key: "tov", label: "TOV", title: "Turnovers" },
  { key: "fg_pct", label: "FG%", title: "Field Goal %", fmt: fmtPct },
  { key: "fg3_pct", label: "3P%", title: "3-Point %", fmt: fmtPct },
  { key: "ft_pct", label: "FT%", title: "Free Throw %", fmt: fmtPct },
];

export default function LineupTable({ lineups, showGame, showDate }) {
  const navigate = useNavigate();

  if (!lineups || lineups.length === 0) {
    return <div className="empty-state">No lineups to display.</div>;
  }

  return (
    <div className="table-wrap">
      <table className="table lineup-table">
        <thead>
          <tr>
            {showDate && <th>Date</th>}
            {showGame && <th>Game</th>}
            <th className="players-col">Lineup</th>
            {COLS.map((c) => (
              <th key={c.key} title={c.title}>{c.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {lineups.map((l, i) => (
            <tr
              key={l.id ?? i}
              className={`table-row ${showGame ? "clickable" : ""}`}
              onClick={() => showGame && navigate(`/games/${l.game_id}`)}
            >
              {showDate && (
                <td className="date-cell">{formatDate(l.game_date)}</td>
              )}
              {showGame && (
                <td className="matchup-cell">{l.matchup}</td>
              )}
              <td className="players-cell">
                <div className="player-list">
                  {l.players.filter(Boolean).map((name, idx) => (
                    <span key={idx} className="player-name">{name}</span>
                  ))}
                </div>
              </td>
              {COLS.map((c) => {
                const val = l[c.key];
                const display = c.fmt ? c.fmt(val) : (val ?? "—");
                const cls = c.key === "plus_minus" ? pmClass(val) : "";
                return (
                  <td key={c.key} className={`stat-cell ${cls}`}>
                    {display}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function fmtPM(v) {
  if (v == null) return "—";
  const n = Number(v);
  if (n > 0) return `+${n}`;
  return String(n);
}

function fmtPct(v) {
  if (v == null) return "—";
  return `${v}%`;
}

function pmClass(v) {
  if (v == null) return "";
  return v > 0 ? "positive" : v < 0 ? "negative" : "";
}

function formatDate(iso) {
  const d = new Date(iso + "T12:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}
