import importlib
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter


def _create_pdf(path: Path, pages: int = 2) -> None:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=300, height=400)
    with path.open("wb") as f:
        writer.write(f)


def _build_app(tmp_path: Path):
    import backend.app.db as db

    db.DB_PATH = tmp_path / "paper_reader.db"
    db.init_db()

    if "backend.app.main" in sys.modules:
        del sys.modules["backend.app.main"]
    main = importlib.import_module("backend.app.main")
    return main.app, db


def test_pdf_page_endpoint_and_count(tmp_path: Path) -> None:
    app, db = _build_app(tmp_path)
    pdf_path = tmp_path / "sample.pdf"
    _create_pdf(pdf_path, pages=2)

    with db.get_conn() as conn:
        cursor = conn.execute(
            """
            INSERT INTO papers (title, canonical_title, content_fingerprint, filename, filepath, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """,
            ("Test Paper", "test paper", "abc123", "sample.pdf", str(pdf_path), "completed"),
        )
        paper_id = cursor.lastrowid

    client = TestClient(app)

    detail = client.get(f"/api/papers/{paper_id}")
    assert detail.status_code == 200
    assert detail.json()["page_count"] == 2

    page1 = client.get(f"/api/papers/{paper_id}/pdf/page/1")
    assert page1.status_code == 200
    assert page1.headers["content-type"].startswith("application/pdf")
    reader = PdfReader(page1.content)
    assert len(reader.pages) == 1

    missing = client.get(f"/api/papers/{paper_id}/pdf/page/3")
    assert missing.status_code == 404
