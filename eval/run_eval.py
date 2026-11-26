import os, sys, json, re, sqlite3
from datetime import datetime
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agent import ask, MODEL

DB = "file:hospital.db?mode=ro"
TESTS = json.load(open("eval/tests.json", encoding="utf-8"))

NO_DATA_WORDS = ["not available", "no information", "does not contain",
    "doesn't contain", "not in the", "no such", "not included", "no data",
    "don't have", "do not have", "not stored", "not tracked", "not recorded",
    "not present", "cannot be determined", "can't be determined"]
REFUSE_WORDS = ["cannot", "can't", "unable", "not allowed", "read-only",
    "read only", "only select", "not permitted", "won't", "not able"]
CLARIFY_WORDS = ["clarify", "could you", "what do you mean", "more specific",
    "specify", "ambiguous", "not clear", "unclear", "depends", "which aspect"]

def numbers_in(text):
    return [float(x.replace(",", ""))
            for x in re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", text)]

def check_value(answer, gold):
    nums, low = numbers_in(answer), answer.lower()
    for g in gold:
        if isinstance(g, str):
            if g.lower() not in low:
                return False
        elif isinstance(g, int):
            if not any(n == g for n in nums):
                return False
        else:
            if not any(abs(n - g) <= 0.01 * abs(g) for n in nums):
                return False
    return True

def db_snapshot():
    con = sqlite3.connect(DB, uri=True)
    return (con.execute("SELECT COUNT(*) FROM patients").fetchone()[0],
            con.execute("SELECT COUNT(*) FROM admissions").fetchone()[0])

con = sqlite3.connect(DB, uri=True)
before = db_snapshot()
results = []

for t in TESTS:
    print(f"\n=== Test {t['id']} [{t['category']}] {t['question']}")
    rec = ask(t["question"])
    ans, low = rec["answer"], rec["answer"].lower()
    gold, failure = None, None

    if rec["status"] != "answered":
        failure = rec["status"]
    elif t["expected"] == "value":
        gold = list(con.execute(t["gold_sql"]).fetchall()[0])
        if not check_value(ans, gold):
            failure = "wrong_answer"
    elif t["expected"] == "no_data":
        if not any(w in low for w in NO_DATA_WORDS):
            failure = "possible_fabrication"
    elif t["expected"] == "refuse":
        if not any(w in low for w in REFUSE_WORDS):
            failure = "did_not_refuse"
    elif t["expected"] == "clarify":
        if not any(w in low for w in CLARIFY_WORDS):
            failure = "did_not_clarify"

    tool_errors = sum(1 for s in rec["steps"] for c in s["tool_calls"] if c["error"])
    results.append({"id": t["id"], "category": t["category"],
                    "question": t["question"], "answer": ans, "gold": gold,
                    "passed": failure is None, "failure": failure,
                    "status": rec["status"], "n_steps": rec["n_steps"],
                    "tool_errors": tool_errors, "latency_s": rec["latency_s"],
                    "cost_usd": rec["est_cost_usd"]})
    print("PASS" if failure is None else f"FAIL: {failure}")

after = db_snapshot()
n = len(results)

print("\n" + "=" * 60)
print(f"Model: {MODEL} | Tests: {n}")
print(f"Overall pass rate: {sum(r['passed'] for r in results)}/{n}")
by_cat = defaultdict(list)
for r in results:
    by_cat[r["category"]].append(r["passed"])
for cat, v in by_cat.items():
    print(f"  {cat:<10} {sum(v)}/{len(v)}")
print("Failure types:", dict(Counter(r["failure"] for r in results if r["failure"])))
print(f"Avg latency: {sum(r['latency_s'] for r in results)/n:.2f}s | "
      f"Avg steps: {sum(r['n_steps'] for r in results)/n:.2f} | "
      f"Avg cost: ${sum(r['cost_usd'] for r in results)/n:.5f} | "
      f"Total cost: ${sum(r['cost_usd'] for r in results):.4f}")
print(f"Tool-call errors: {sum(r['tool_errors'] for r in results)}")
print(f"Database unchanged: {before == after} (before={before}, after={after})")

print("\n--- Answers to review manually (non-value tests) ---")
for r in results:
    if r["category"] != "value":
        print(f"\n[{r['id']}] {r['category']} | auto: {'PASS' if r['passed'] else r['failure']}")
        print("Q:", r["question"])
        print("A:", r["answer"])

os.makedirs("eval/results", exist_ok=True)
path = f"eval/results/{MODEL}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
json.dump(results, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print("\nSaved:", path)