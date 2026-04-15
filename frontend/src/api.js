import axios from "axios";

// In dev, empty string → Vite proxy to localhost:8000
// In production, set VITE_API_URL to your Railway backend URL
const BASE = import.meta.env.VITE_API_URL || "";

export const api = {
  status: () => axios.get(`${BASE}/api/status`).then((r) => r.data),
  triggerSync: (maxGames) =>
    axios.post(`${BASE}/api/sync${maxGames ? `?max_games=${maxGames}` : ""}`).then((r) => r.data),
  teams: () => axios.get(`${BASE}/api/teams`).then((r) => r.data),
  games: (teamId) =>
    axios.get(`${BASE}/api/games${teamId ? `?team_id=${teamId}` : ""}`).then((r) => r.data),
  gameLineups: (gameId, teamId) =>
    axios
      .get(`${BASE}/api/games/${gameId}/lineups${teamId ? `?team_id=${teamId}` : ""}`)
      .then((r) => r.data),
  searchPlayers: (q) =>
    axios.get(`${BASE}/api/players/search?q=${encodeURIComponent(q)}`).then((r) => r.data),
  searchLineups: (playerIds, teamId) =>
    axios
      .get(
        `${BASE}/api/lineups/search?player_ids=${playerIds.join(",")}${teamId ? `&team_id=${teamId}` : ""}`
      )
      .then((r) => r.data),
  lineupTotals: (playerIds, teamId) =>
    axios
      .get(
        `${BASE}/api/lineups/totals?player_ids=${playerIds.join(",")}${teamId ? `&team_id=${teamId}` : ""}`
      )
      .then((r) => r.data),
};
