"""
FastAPI backend for NBA Lineup Stats.
"""

import math
import os
import threading
import logging
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, func, or_
from sqlalchemy.orm import Session, sessionmaker

from models import Base, Team, Game, Player, LineupStat

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DB setup
# ---------------------------------------------------------------------------
DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "lineups.db"))
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="NBA Lineup Stats", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Background sync state
# ---------------------------------------------------------------------------
sync_status = {"running": False, "message": "Idle", "games_done": 0, "games_total": 0}


def _run_sync_background(max_games: Optional[int] = None):
    from fetcher import run_sync
    sync_status["running"] = True
    sync_status["message"] = "Syncing…"
    try:
        db = SessionLocal()
        run_sync(db, max_games=max_games)
        sync_status["message"] = "Sync complete"
    except Exception as e:
        sync_status["message"] = f"Error: {e}"
        log.exception("Sync failed")
    finally:
        sync_status["running"] = False
        try:
            db.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fmt_minutes(seconds: int) -> str:
    m = seconds // 60
    s = seconds % 60
    return f"{m}:{s:02d}"


def lineup_stat_to_dict(ls: LineupStat, game: Game, home_team: Team, away_team: Team) -> dict:
    fgpct = round(ls.fgm / ls.fga * 100, 1) if ls.fga else None
    fg3pct = round(ls.fg3m / ls.fg3a * 100, 1) if ls.fg3a else None
    ftpct = round(ls.ftm / ls.fta * 100, 1) if ls.fta else None
    return {
        "id": ls.id,
        "game_id": ls.game_id,
        "game_date": game.game_date.isoformat(),
        "matchup": f"{away_team.abbreviation} @ {home_team.abbreviation}",
        "home_score": game.home_score,
        "away_score": game.away_score,
        "team_id": ls.team_id,
        "players": [
            ls.player1_name, ls.player2_name, ls.player3_name,
            ls.player4_name, ls.player5_name,
        ],
        "player_ids": [
            ls.player1_id, ls.player2_id, ls.player3_id,
            ls.player4_id, ls.player5_id,
        ],
        "minutes": fmt_minutes(ls.minutes_seconds or 0),
        "minutes_seconds": ls.minutes_seconds or 0,
        "plus_minus": ls.plus_minus,
        "pts": ls.pts,
        "reb": ls.reb,
        "ast": ls.ast,
        "stl": ls.stl,
        "blk": ls.blk,
        "tov": ls.tov,
        "fgm": ls.fgm,
        "fga": ls.fga,
        "fg_pct": fgpct,
        "fg3m": ls.fg3m,
        "fg3a": ls.fg3a,
        "fg3_pct": fg3pct,
        "ftm": ls.ftm,
        "fta": ls.fta,
        "ft_pct": ftpct,
        "oreb": ls.oreb,
        "dreb": ls.dreb,
        "lineup_key": ls.lineup_key,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/api/status")
def get_status():
    return sync_status


@app.post("/api/sync")
def trigger_sync(max_games: Optional[int] = Query(None), background_tasks: BackgroundTasks = None):
    if sync_status["running"]:
        return {"message": "Sync already running"}
    background_tasks.add_task(_run_sync_background, max_games)
    return {"message": "Sync started"}


@app.get("/api/teams")
def list_teams(db: Session = Depends(get_db)):
    teams = db.query(Team).order_by(Team.name).all()
    return [{"id": t.id, "name": t.name, "abbreviation": t.abbreviation, "city": t.city} for t in teams]


@app.get("/api/games")
def list_games(
    team_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Game).filter(Game.season == "2025-26")
    if team_id:
        q = q.filter(or_(Game.home_team_id == team_id, Game.away_team_id == team_id))
    q = q.order_by(Game.game_date)
    games = q.all()

    result = []
    for g in games:
        home = db.get(Team, g.home_team_id)
        away = db.get(Team, g.away_team_id)
        result.append({
            "id": g.id,
            "game_date": g.game_date.isoformat(),
            "home_team": {"id": home.id, "abbreviation": home.abbreviation, "name": home.name} if home else None,
            "away_team": {"id": away.id, "abbreviation": away.abbreviation, "name": away.name} if away else None,
            "home_score": g.home_score,
            "away_score": g.away_score,
            "data_fetched": g.data_fetched,
        })
    return result


@app.get("/api/games/{game_id}/lineups")
def game_lineups(
    game_id: str,
    team_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    if not game.data_fetched:
        raise HTTPException(404, "Lineup data not yet fetched for this game")

    home = db.get(Team, game.home_team_id)
    away = db.get(Team, game.away_team_id)

    q = db.query(LineupStat).filter_by(game_id=game_id)
    if team_id:
        q = q.filter_by(team_id=team_id)
    lineups = q.order_by(LineupStat.minutes_seconds.desc()).all()

    return [lineup_stat_to_dict(ls, game, home, away) for ls in lineups]


@app.get("/api/players/search")
def search_players(q: str, db: Session = Depends(get_db)):
    """Return players whose name matches the query string (partial, case-insensitive)."""
    q_lower = q.lower().strip()
    players = (
        db.query(Player)
        .filter(Player.name_normalized.contains(q_lower))
        .order_by(Player.name)
        .limit(20)
        .all()
    )
    return [{"id": p.id, "name": p.name} for p in players]


@app.get("/api/lineups/search")
def search_lineups(
    player_ids: str = Query(..., description="Comma-separated player IDs (2–5 players)"),
    team_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """
    Find all lineup stat rows that include ALL of the given player IDs.
    Supports 2–5 players (partial lineup search).
    """
    try:
        pids = [int(x.strip()) for x in player_ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(400, "Invalid player_ids")

    if len(pids) < 2:
        raise HTTPException(400, "Provide at least 2 player IDs")
    if len(pids) > 5:
        pids = pids[:5]

    # Build filter: each pid must appear as one of the 5 player columns
    pid_cols = [
        LineupStat.player1_id,
        LineupStat.player2_id,
        LineupStat.player3_id,
        LineupStat.player4_id,
        LineupStat.player5_id,
    ]

    q_obj = db.query(LineupStat)
    for pid in pids:
        q_obj = q_obj.filter(or_(*[col == pid for col in pid_cols]))

    if team_id:
        q_obj = q_obj.filter_by(team_id=team_id)

    rows = q_obj.order_by(LineupStat.game_id).all()  # will sort by date after join

    result = []
    for ls in rows:
        game = db.get(Game, ls.game_id)
        if not game:
            continue
        home = db.get(Team, game.home_team_id)
        away = db.get(Team, game.away_team_id)
        result.append(lineup_stat_to_dict(ls, game, home, away))

    # Sort by date
    result.sort(key=lambda x: x["game_date"])
    return result


@app.get("/api/lineups/totals")
def lineup_totals(
    player_ids: str = Query(..., description="Comma-separated player IDs (2–5 players)"),
    team_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Aggregate stats for a lineup across all games."""
    rows_response = search_lineups(player_ids=player_ids, team_id=team_id, db=db)
    if not rows_response:
        return {"games": 0}

    totals: dict = {
        "games": len(rows_response),
        "minutes_seconds": sum(r["minutes_seconds"] for r in rows_response),
        "plus_minus": sum(r["plus_minus"] or 0 for r in rows_response),
        "pts": sum(r["pts"] or 0 for r in rows_response),
        "reb": sum(r["reb"] or 0 for r in rows_response),
        "ast": sum(r["ast"] or 0 for r in rows_response),
        "stl": sum(r["stl"] or 0 for r in rows_response),
        "blk": sum(r["blk"] or 0 for r in rows_response),
        "tov": sum(r["tov"] or 0 for r in rows_response),
        "fgm": sum(r["fgm"] or 0 for r in rows_response),
        "fga": sum(r["fga"] or 0 for r in rows_response),
        "fg3m": sum(r["fg3m"] or 0 for r in rows_response),
        "fg3a": sum(r["fg3a"] or 0 for r in rows_response),
        "ftm": sum(r["ftm"] or 0 for r in rows_response),
        "fta": sum(r["fta"] or 0 for r in rows_response),
    }
    totals["minutes"] = fmt_minutes(totals["minutes_seconds"])
    totals["fg_pct"] = round(totals["fgm"] / totals["fga"] * 100, 1) if totals["fga"] else None
    totals["fg3_pct"] = round(totals["fg3m"] / totals["fg3a"] * 100, 1) if totals["fg3a"] else None
    totals["ft_pct"] = round(totals["ftm"] / totals["fta"] * 100, 1) if totals["fta"] else None
    return totals
