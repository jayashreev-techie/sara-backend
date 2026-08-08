"""Inspect sara_dev_admin schema (web app DB)."""
import pymysql

conn = pymysql.connect(host="localhost", user="root", password="", database="sara_dev_admin")
cur = conn.cursor()

cur.execute("SHOW TABLES")
tables = [r[0] for r in cur.fetchall()]
print("=== ALL TABLES ===")
for t in tables:
    print(" ", t)

interesting = [t for t in tables if any(k in t.lower() for k in
    ["work", "client", "store", "product", "location", "user", "recee", "install", "design", "fabric"])]

for t in interesting:
    print(f"\n=== {t} ===")
    cur.execute(f"DESCRIBE `{t}`")
    for row in cur.fetchall():
        # Field, Type, Null, Key, Default, Extra
        print(f"  {row[0]:35} {row[1]:25} null={row[2]:4} key={row[3] or '-':4} default={row[4]}")
    cur.execute(f"SELECT COUNT(*) FROM `{t}`")
    print(f"  -> {cur.fetchone()[0]} rows")

conn.close()
