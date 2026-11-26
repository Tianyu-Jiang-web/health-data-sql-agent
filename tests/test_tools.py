import os, sys, json, sqlite3, subprocess
import pytest
from tools import DB, run_sql, run_tool, schema_context


@pytest.fixture(scope="session", autouse=True)
def database():
    """Make sure the synthetic database exists before any test runs."""
    if not os.path.exists("hospital.db"):
        subprocess.run([sys.executable, "make_db.py"], check=True)


def row_counts():
    con = sqlite3.connect(DB, uri=True)
    return (con.execute("SELECT COUNT(*) FROM patients").fetchone()[0],
            con.execute("SELECT COUNT(*) FROM admissions").fetchone()[0])


# ---------- normal use ----------

def test_select_returns_json():
    out = json.loads(run_sql("SELECT COUNT(*) FROM admissions"))
    assert out["rows"] == [[1200]]


def test_select_tolerates_case_and_whitespace():
    out = json.loads(run_sql("   select count(*) from patients ;  "))
    assert out["rows"] == [[500]]


def test_result_is_capped_at_50_rows():
    out = json.loads(run_sql("SELECT * FROM admissions"))
    assert len(out["rows"]) == 50


def test_bad_sql_returns_error_instead_of_crashing():
    assert run_sql("SELECT income FROM patients").startswith("Error")


def test_unknown_tool_returns_error():
    assert run_tool("drop_everything", {}).startswith("Error")


# ---------- layer 1: code-level check ----------

@pytest.mark.parametrize("sql", [
    "DROP TABLE patients",
    "DELETE FROM admissions",
    "INSERT INTO patients VALUES (9999, 'F', 1990)",
    "UPDATE admissions SET los_days = 1",
    "SELECT 1; DROP TABLE patients",
    "PRAGMA writable_schema = 1",
])
def test_write_and_multi_statements_are_rejected(sql):
    before = row_counts()
    assert run_sql(sql).startswith("Error")
    assert row_counts() == before


# ---------- layer 2: read-only database connection ----------

def test_readonly_connection_blocks_writes_even_without_code_check():
    """Bypass run_sql entirely: the connection itself must refuse writes."""
    con = sqlite3.connect(DB, uri=True)
    with pytest.raises(sqlite3.OperationalError):
        con.execute("DELETE FROM admissions")
    assert row_counts() == (500, 1200)


# ---------- known limitations (documented, not bugs to hide) ----------

def test_known_limitation_cte_is_rejected():
    """A valid read-only query starting with WITH is rejected by the
    code-level check. This is conservative on purpose."""
    assert run_sql("WITH t AS (SELECT 1) SELECT * FROM t").startswith("Error")


def test_known_limitation_semicolon_in_string_is_rejected():
    """A semicolon inside a string literal also triggers the check."""
    assert run_sql("SELECT ';'").startswith("Error")


# ---------- schema grounding used by v3 ----------

def test_schema_context_lists_actual_values():
    ctx = schema_context()
    assert "'F', 'M'" in ctx
    assert "'ICU'" in ctx