import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "paper_reader.db"


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS papers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                filename TEXT NOT NULL,
                filepath TEXT NOT NULL,
                status TEXT NOT NULL,
                summary_json TEXT,
                full_text TEXT,
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
