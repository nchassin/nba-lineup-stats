"""
Startup script: downloads the populated SQLite database from GitHub releases
if it isn't already present or is empty. Runs before uvicorn starts.
"""
import os
import gzip
import shutil
import urllib.request

DB_URL = "https://github.com/nchassin/nba-lineup-stats/releases/download/v1.1/lineups.db.gz"
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lineups.db")

MIN_SIZE = 1_000_000  # 1 MB — empty schema is ~30 KB, full DB is ~9.5 MB

if not os.path.exists(DB_PATH) or os.path.getsize(DB_PATH) < MIN_SIZE:
    print(f"Downloading database from GitHub releases...")
    tmp = DB_PATH + ".gz"
    urllib.request.urlretrieve(DB_URL, tmp)
    with gzip.open(tmp, "rb") as gz_in, open(DB_PATH, "wb") as db_out:
        shutil.copyfileobj(gz_in, db_out)
    os.remove(tmp)
    print(f"Database ready: {os.path.getsize(DB_PATH) / 1e6:.1f} MB")
else:
    print(f"Database already present: {os.path.getsize(DB_PATH) / 1e6:.1f} MB")
