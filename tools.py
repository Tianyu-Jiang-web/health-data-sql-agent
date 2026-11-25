import sqlite3, json

DB = "file:hospital.db?mode=ro"   # 只读连接,从数据库层面禁止写入

def describe_tables() -> str:
    con = sqlite3.connect(DB, uri=True)
    rows = con.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='table'").fetchall()
    return json.dumps(rows)

def run_sql(query: str) -> str:
    q = query.strip().rstrip(";")
    if not q.lower().startswith("select") or ";" in q:
        return "Error: only a single SELECT statement is allowed."
    try:
        con = sqlite3.connect(DB, uri=True)
        cur = con.execute(q)
        cols = [c[0] for c in cur.description]
        rows = cur.fetchmany(50)            # 最多返回 50 行
        return json.dumps({"columns": cols, "rows": rows})
    except Exception as e:
        return f"Error: {e}"                # 把报错返回给模型,让它自己改

TOOL_DEFS = [
    {"type": "function", "function": {
        "name": "describe_tables",
        "description": "Return the schema of all tables in the hospital database.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "run_sql",
        "description": "Run one read-only SQLite SELECT query. Returns at most 50 rows.",
        "parameters": {"type": "object",
                       "properties": {"query": {"type": "string"}},
                       "required": ["query"]}}},
]

def run_tool(name, args):
    if name == "describe_tables":
        return describe_tables()
    if name == "run_sql":
        return run_sql(args["query"])
    return f"Error: unknown tool {name}"