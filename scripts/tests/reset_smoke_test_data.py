#!/usr/bin/env python

import sqlite3
import os

DB_PATH = "sentinelai-test.db"
MISSION_ID = "Smoke Test Mission"
SOURCE = "smoke-test"

if not os.path.exists(DB_PATH):
    print(f"Database not found at {DB_PATH}")
    exit(1)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Delete events created by the smoke test
cur.execute(
    """
    DELETE FROM events
    WHERE mission_id = ?
      OR source = ?
    """,
    (MISSION_ID, SOURCE),
)

conn.commit()
conn.close()

print(f"Removed smoke-test events from the database at {DB_PATH}.")
