import json, sqlite3

import os
tests = json.load(open(os.getenv("TESTS_FILE", "eval/tests.json"), encoding="utf-8"))
con = sqlite3.connect("file:hospital.db?mode=ro", uri=True)

for t in tests:
    print(f"{t['id']:>2} [{t['category']}] {t['question']}")
    if t["gold_sql"]:
        print("    gold ->", con.execute(t["gold_sql"]).fetchall())
    else:
        print("    expected behaviour:", t["expected"])