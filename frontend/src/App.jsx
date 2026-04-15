import { Routes, Route, NavLink } from "react-router-dom";
import GamesPage from "./pages/GamesPage";
import GameDetailPage from "./pages/GameDetailPage";
import LineupSearchPage from "./pages/LineupSearchPage";
import AdminPage from "./pages/AdminPage";
import "./App.css";

export default function App() {
  return (
    <div className="app">
      <header className="header">
        <div className="header-inner">
          <span className="logo">NBA Lineup Stats · 2025-26</span>
          <nav className="nav">
            <NavLink to="/" end className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
              Games
            </NavLink>
            <NavLink to="/search" className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
              Lineup Search
            </NavLink>
            <NavLink to="/admin" className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
              Data Sync
            </NavLink>
          </nav>
        </div>
      </header>
      <main className="main">
        <Routes>
          <Route path="/" element={<GamesPage />} />
          <Route path="/games/:gameId" element={<GameDetailPage />} />
          <Route path="/search" element={<LineupSearchPage />} />
          <Route path="/admin" element={<AdminPage />} />
        </Routes>
      </main>
    </div>
  );
}
