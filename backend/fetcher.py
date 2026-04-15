"""
NBA lineup data fetcher for the 2025-26 season.

Data sources (all from nba_api):
  - nba_api.stats: leaguegamelog (game list), leaguedashlineups (box stats per lineup)
  - nba_api.live:  boxscore (starters + player IDs), playbyplay (substitution events)

Lineup reconstruction strategy:
  1. Pull boxscore to get starting 5 for each team + all player names.
  2. Pull live play-by-play; walk events in order by orderNumber.
  3. Track the active 5-man unit per team; record elapsed seconds per segment.
  4. Compute +/- from embedded scoreHome/scoreAway on each action.
  5. Attach pts/reb/ast/etc from leaguedashlineups (date-filtered to this game).
"""

import re
import time
import unicodedata
import logging
from typing import Optional

from sqlalchemy.orm import Session

from nba_api.stats.endpoints import leaguegamelog, leaguedashlineups
from nba_api.stats.static import teams as nba_teams_static
from nba_api.live.nba.endpoints import boxscore as live_boxscore
from nba_api.live.nba.endpoints import playbyplay as live_pbp

from models import Base, Team, Game, Player, LineupStat

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SEASON = "2025-26"
DELAY = 0.7  # seconds between API calls


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_name(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = nfkd.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z ]", "", ascii_name.lower()).strip()


def parse_clock(clock_str: str) -> float:
    """'PT07M03.00S' → total seconds remaining in the period."""
    m = re.match(r"PT(\d+)M([\d.]+)S", clock_str or "")
    if not m:
        return 0.0
    return int(m.group(1)) * 60 + float(m.group(2))


def clock_to_elapsed(clock_str: str, period: int) -> int:
    """Convert a clock string + period to absolute game-seconds elapsed (integer)."""
    remaining = parse_clock(clock_str)
    if period <= 4:
        period_length = 12 * 60
        period_start = (period - 1) * 720
    else:
        period_length = 5 * 60
        period_start = 4 * 720 + (period - 5) * 300
    return int(period_start + (period_length - remaining))


def lineup_key(player_ids: list) -> str:
    return "_".join(str(p) for p in sorted(player_ids))


# ---------------------------------------------------------------------------
# Team sync
# ---------------------------------------------------------------------------

def sync_teams(session: Session):
    all_teams = nba_teams_static.get_teams()
    for t in all_teams:
        existing = session.get(Team, t["id"])
        if not existing:
            session.add(Team(
                id=t["id"],
                abbreviation=t["abbreviation"],
                name=t["full_name"],
                city=t["city"],
            ))
    session.commit()
    log.info("Teams synced: %d", len(all_teams))


# ---------------------------------------------------------------------------
# Game log sync
# ---------------------------------------------------------------------------

def sync_game_log(session: Session):
    log.info("Fetching league game log for %s …", SEASON)
    gl = leaguegamelog.LeagueGameLog(
        season=SEASON,
        season_type_all_star="Regular Season",
    )
    time.sleep(DELAY)
    df = gl.get_data_frames()[0]

    if df.empty:
        log.warning("Game log is empty — season may not have started yet.")
        return

    seen_game_ids = set()
    for _, row in df.iterrows():
        game_id = str(row["GAME_ID"])
        if game_id in seen_game_ids:
            continue
        seen_game_ids.add(game_id)

        if session.get(Game, game_id):
            continue

        try:
            from datetime import datetime
            raw_date = str(row["GAME_DATE"])
            try:
                game_date = datetime.strptime(raw_date, "%Y-%m-%dT%H:%M:%S").date()
            except ValueError:
                game_date = datetime.strptime(raw_date[:10], "%Y-%m-%d").date()
        except Exception:
            continue

        matchup = str(row.get("MATCHUP", ""))
        team_id = int(row["TEAM_ID"])

        if " vs. " in matchup:
            home_team_id = team_id
            away_abbr = matchup.split(" vs. ")[-1].strip()
            away_team = session.query(Team).filter_by(abbreviation=away_abbr).first()
            away_team_id = away_team.id if away_team else None
        else:
            away_team_id = team_id
            home_abbr = matchup.split(" @ ")[-1].strip()
            home_team = session.query(Team).filter_by(abbreviation=home_abbr).first()
            home_team_id = home_team.id if home_team else None

        session.merge(Game(
            id=game_id,
            season=SEASON,
            game_date=game_date,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
        ))

    session.commit()
    log.info("Game log synced: %d unique games", len(seen_game_ids))


# ---------------------------------------------------------------------------
# Player upsert
# ---------------------------------------------------------------------------

def upsert_player(session: Session, player_id: int, name: str) -> "Player":
    p = session.get(Player, player_id)
    if not p:
        p = Player(id=player_id, name=name, name_normalized=normalize_name(name))
        session.add(p)
    return p


# ---------------------------------------------------------------------------
# Core: fetch one game
# ---------------------------------------------------------------------------

def fetch_game_lineups(session: Session, game: Game):
    log.info("Processing game %s (%s) …", game.id, game.game_date)

    # ---- 1. Live boxscore: starters + roster ----
    try:
        bs = live_boxscore.BoxScore(game_id=game.id)
        time.sleep(DELAY)
        bs_data = bs.get_dict()["game"]
    except Exception as e:
        log.warning("Boxscore fetch failed for %s: %s", game.id, e)
        return

    home_team_id = bs_data["homeTeam"]["teamId"]
    away_team_id = bs_data["awayTeam"]["teamId"]
    home_score = int(bs_data["homeTeam"].get("score", 0) or 0)
    away_score = int(bs_data["awayTeam"].get("score", 0) or 0)

    # Update game record
    game.home_team_id = home_team_id
    game.away_team_id = away_team_id
    game.home_score = home_score
    game.away_score = away_score

    # Build player roster: id → name, id → team_id
    player_team: dict[int, int] = {}
    starters: dict[int, list[int]] = {home_team_id: [], away_team_id: []}

    for side in ("homeTeam", "awayTeam"):
        team_id = bs_data[side]["teamId"]
        for p in bs_data[side].get("players", []):
            pid = int(p["personId"])
            name = p.get("name", "Unknown")
            player_team[pid] = team_id
            upsert_player(session, pid, name)
            if str(p.get("starter", "0")) == "1":
                starters[team_id].append(pid)

    session.flush()

    # ---- 2. Live play-by-play ----
    try:
        pbp = live_pbp.PlayByPlay(game_id=game.id)
        time.sleep(DELAY)
        actions = pbp.get_dict()["game"]["actions"]
    except Exception as e:
        log.warning("PBP fetch failed for %s: %s", game.id, e)
        return

    # Sort by orderNumber to ensure correct sequence
    actions = sorted(actions, key=lambda a: a.get("orderNumber", 0))

    # ---- 3. Reconstruct lineups ----
    home_lineup: list[int] = list(starters.get(home_team_id, []))
    away_lineup: list[int] = list(starters.get(away_team_id, []))

    # lineup_time: {(team_id, lk): {"player_ids": [...], "seconds": int}}
    lineup_time: dict[tuple, dict] = {}
    current_time = 0

    # Track score at the START of each lineup segment (for +/- computation)
    seg_home_score = 0
    seg_away_score = 0

    # plus_minus accumulation: {(team_id, lk): float}
    pm_acc: dict[tuple, float] = {}

    def record_segment(start: int, end: int, h_score_end: int, a_score_end: int):
        """Record a lineup segment and its score differential."""
        nonlocal seg_home_score, seg_away_score, current_time
        if start >= end:
            return
        duration = end - start
        h_diff = (h_score_end - seg_home_score) - (a_score_end - seg_away_score)
        a_diff = -h_diff

        for team_id, lineup, diff in [
            (home_team_id, home_lineup, h_diff),
            (away_team_id, away_lineup, a_diff),
        ]:
            if len(lineup) != 5:
                continue
            lk = lineup_key(lineup)
            key = (team_id, lk)
            if key not in lineup_time:
                lineup_time[key] = {"player_ids": sorted(lineup), "seconds": 0}
                pm_acc[key] = 0.0
            lineup_time[key]["seconds"] += duration
            pm_acc[key] += diff

        # Update segment start scores and time
        seg_home_score = h_score_end
        seg_away_score = a_score_end
        current_time = end

    def parse_score(val, fallback: int) -> int:
        try:
            return int(val)
        except (TypeError, ValueError):
            return fallback

    latest_home = 0
    latest_away = 0

    for action in actions:
        a_type = action.get("actionType", "")
        period = int(action.get("period", 1) or 1)
        clock = action.get("clock", "PT12M00.00S") or "PT12M00.00S"
        event_time = clock_to_elapsed(clock, period)

        h_score = parse_score(action.get("scoreHome"), latest_home)
        a_score = parse_score(action.get("scoreAway"), latest_away)
        latest_home = h_score
        latest_away = a_score

        if a_type == "substitution":
            sub_type = action.get("subType", "")
            pid = int(action.get("personId", 0) or 0)
            team_id = int(action.get("teamId", 0) or 0)

            # Record segment up to this substitution point
            record_segment(current_time, event_time, h_score, a_score)

            if sub_type == "out":
                if team_id == home_team_id:
                    home_lineup = [p for p in home_lineup if p != pid]
                elif team_id == away_team_id:
                    away_lineup = [p for p in away_lineup if p != pid]
            elif sub_type == "in":
                if team_id == home_team_id and pid not in home_lineup:
                    home_lineup.append(pid)
                elif team_id == away_team_id and pid not in away_lineup:
                    away_lineup.append(pid)

        elif a_type == "period" and action.get("subType") == "end":
            record_segment(current_time, event_time, h_score, a_score)

    # Record final segment to end of game
    if actions:
        last = actions[-1]
        last_period = int(last.get("period", 4) or 4)
        if last_period <= 4:
            game_end = 4 * 720
        else:
            game_end = 4 * 720 + (last_period - 4) * 300
        record_segment(current_time, game_end, home_score, away_score)

    # ---- 4. Pull box stats from leaguedashlineups ----
    lineup_stats_map: dict[str, dict] = {}
    date_str = game.game_date.strftime("%m/%d/%Y")

    for team_id in [home_team_id, away_team_id]:
        try:
            ld = leaguedashlineups.LeagueDashLineups(
                team_id_nullable=team_id,
                season=SEASON,
                season_type_all_star="Regular Season",
                measure_type_detailed_defense="Base",
                per_mode_detailed="Totals",
                date_from_nullable=date_str,
                date_to_nullable=date_str,
                group_quantity=5,
            )
            time.sleep(DELAY)
            ld_df = ld.get_data_frames()[0]
            for _, row in ld_df.iterrows():
                try:
                    group_id = str(row.get("GROUP_ID", ""))
                    # GROUP_ID format: "-1629028-1629029-1629060-1629216-1630559-"
                    ids = [int(x) for x in group_id.split("-") if x.strip()]
                    lk = lineup_key(ids)
                    lineup_stats_map[lk] = {
                        "pts": float(row.get("PTS", 0) or 0),
                        "reb": float(row.get("REB", 0) or 0),
                        "ast": float(row.get("AST", 0) or 0),
                        "stl": float(row.get("STL", 0) or 0),
                        "blk": float(row.get("BLK", 0) or 0),
                        "tov": float(row.get("TOV", 0) or 0),
                        "fgm": float(row.get("FGM", 0) or 0),
                        "fga": float(row.get("FGA", 0) or 0),
                        "fg3m": float(row.get("FG3M", 0) or 0),
                        "fg3a": float(row.get("FG3A", 0) or 0),
                        "ftm": float(row.get("FTM", 0) or 0),
                        "fta": float(row.get("FTA", 0) or 0),
                        "oreb": float(row.get("OREB", 0) or 0),
                        "dreb": float(row.get("DREB", 0) or 0),
                    }
                except Exception:
                    continue
        except Exception as e:
            log.warning("leaguedashlineups failed for team %s: %s", team_id, e)

    # ---- 5. Write LineupStat rows ----
    for (team_id, lk_str), data in lineup_time.items():
        if data["seconds"] < 1:
            continue
        pids = data["player_ids"]
        if len(pids) != 5:
            continue

        stats = lineup_stats_map.get(lk_str, {})
        pm = pm_acc.get((team_id, lk_str), 0.0)

        players = [session.get(Player, pid) for pid in pids]
        names = [p.name if p else "Unknown" for p in players]

        ls = LineupStat(
            game_id=game.id,
            team_id=team_id,
            player1_id=pids[0], player1_name=names[0],
            player2_id=pids[1], player2_name=names[1],
            player3_id=pids[2], player3_name=names[2],
            player4_id=pids[3], player4_name=names[3],
            player5_id=pids[4], player5_name=names[4],
            minutes_seconds=data["seconds"],
            plus_minus=pm,
            pts=stats.get("pts", 0),
            reb=stats.get("reb", 0),
            ast=stats.get("ast", 0),
            stl=stats.get("stl", 0),
            blk=stats.get("blk", 0),
            tov=stats.get("tov", 0),
            fgm=stats.get("fgm", 0),
            fga=stats.get("fga", 0),
            fg3m=stats.get("fg3m", 0),
            fg3a=stats.get("fg3a", 0),
            ftm=stats.get("ftm", 0),
            fta=stats.get("fta", 0),
            oreb=stats.get("oreb", 0),
            dreb=stats.get("dreb", 0),
            lineup_key=lk_str,
        )
        session.add(ls)

    game.data_fetched = True
    session.commit()
    log.info("Game %s done — %d lineup segments written", game.id, len(lineup_time))


# ---------------------------------------------------------------------------
# Main sync entry point
# ---------------------------------------------------------------------------

def run_sync(session: Session, max_games: Optional[int] = None):
    sync_teams(session)
    sync_game_log(session)

    games_to_fetch = (
        session.query(Game)
        .filter_by(data_fetched=False, season=SEASON)
        .order_by(Game.game_date)
        .all()
    )

    if max_games:
        games_to_fetch = games_to_fetch[:max_games]

    log.info("%d games to process", len(games_to_fetch))
    for i, game in enumerate(games_to_fetch, 1):
        log.info("[%d/%d] %s", i, len(games_to_fetch), game.id)
        fetch_game_lineups(session, game)

    log.info("Sync complete.")
