import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "paper_reader.db"


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
    col_names = {c[1] for c in cols}
    if column not in col_names:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS papers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                canonical_title TEXT,
                content_fingerprint TEXT,
                filename TEXT NOT NULL,
                filepath TEXT NOT NULL,
                status TEXT NOT NULL,
                summary_json TEXT,
                full_text TEXT,
                summary_version INTEGER NOT NULL DEFAULT 0,
                summary_updated_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                source_hint TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (paper_id) REFERENCES papers (id)
            )
            """
        )
        _ensure_column(conn, "papers", "summary_version", "summary_version INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "papers", "summary_updated_at", "summary_updated_at TEXT")
        _ensure_column(conn, "papers", "canonical_title", "canonical_title TEXT")
        _ensure_column(conn, "papers", "content_fingerprint", "content_fingerprint TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_papers_fingerprint ON papers(content_fingerprint)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_papers_canonical_title ON papers(canonical_title)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id INTEGER NOT NULL,
                page_start INTEGER NOT NULL,
                page_end INTEGER NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (paper_id) REFERENCES papers (id)
            )
            """
        )
        conn.commit()


@contextmanager
def get_conn() -> Any:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def to_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False)


def from_json(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    return json.loads(raw)
