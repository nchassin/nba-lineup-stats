from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Date, DateTime, ForeignKey, create_engine, Text
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True)          # NBA team_id
    abbreviation = Column(String(5), nullable=False)
    name = Column(String(100), nullable=False)
    city = Column(String(100), nullable=False)
    games = relationship("Game", back_populates="home_team", foreign_keys="Game.home_team_id")


class Game(Base):
    __tablename__ = "games"
    id = Column(String(20), primary_key=True)       # NBA game_id string e.g. "0022501001"
    season = Column(String(10), nullable=False)      # "2025-26"
    game_date = Column(Date, nullable=False)
    home_team_id = Column(Integer, ForeignKey("teams.id"))
    away_team_id = Column(Integer, ForeignKey("teams.id"))
    home_score = Column(Integer)
    away_score = Column(Integer)
    data_fetched = Column(Boolean, default=False)

    home_team = relationship("Team", foreign_keys=[home_team_id], back_populates="games")
    away_team = relationship("Team", foreign_keys=[away_team_id])
    lineups = relationship("LineupStat", back_populates="game")


class Player(Base):
    __tablename__ = "players"
    id = Column(Integer, primary_key=True)          # NBA person_id
    name = Column(String(100), nullable=False)
    name_normalized = Column(String(100))           # lowercase, no punctuation for search


class LineupStat(Base):
    __tablename__ = "lineup_stats"
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(String(20), ForeignKey("games.id"), nullable=False)
    team_id = Column(Integer, nullable=False)

    # The 5 player IDs sorted ascending so the same lineup always has the same key
    player1_id = Column(Integer, ForeignKey("players.id"))
    player2_id = Column(Integer, ForeignKey("players.id"))
    player3_id = Column(Integer, ForeignKey("players.id"))
    player4_id = Column(Integer, ForeignKey("players.id"))
    player5_id = Column(Integer, ForeignKey("players.id"))

    # Human-readable names (denormalized for fast display)
    player1_name = Column(String(100))
    player2_name = Column(String(100))
    player3_name = Column(String(100))
    player4_name = Column(String(100))
    player5_name = Column(String(100))

    minutes_seconds = Column(Integer)               # total seconds on court
    plus_minus = Column(Float)
    pts = Column(Float, default=0)
    reb = Column(Float, default=0)
    ast = Column(Float, default=0)
    stl = Column(Float, default=0)
    blk = Column(Float, default=0)
    tov = Column(Float, default=0)
    fgm = Column(Float, default=0)
    fga = Column(Float, default=0)
    fg3m = Column(Float, default=0)
    fg3a = Column(Float, default=0)
    ftm = Column(Float, default=0)
    fta = Column(Float, default=0)
    oreb = Column(Float, default=0)
    dreb = Column(Float, default=0)

    # Derived lineup key for fast searching
    lineup_key = Column(String(100), index=True)    # "id1_id2_id3_id4_id5" sorted

    game = relationship("Game", back_populates="lineups")
    p1 = relationship("Player", foreign_keys=[player1_id])
    p2 = relationship("Player", foreign_keys=[player2_id])
    p3 = relationship("Player", foreign_keys=[player3_id])
    p4 = relationship("Player", foreign_keys=[player4_id])
    p5 = relationship("Player", foreign_keys=[player5_id])
