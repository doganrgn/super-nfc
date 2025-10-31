import sqlite3
from datetime import datetime

SHORTID = "ab12cd34"  # istersen değiştir

conn = sqlite3.connect("app.db")
cur = conn.cursor()
cur.execute(
    "INSERT INTO tag (shortid, owner_user_id, status, created_at) VALUES (?, NULL, ?, ?)",
    (SHORTID, "unassigned", datetime.utcnow().isoformat())
)
conn.commit()
conn.close()
print(f"OK: shortid={SHORTID} eklendi")
