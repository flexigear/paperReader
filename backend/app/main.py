from datetime import datetime
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .db import from_json, get_conn, init_db
from .schemas import ChatMessageIn, ChatMessageOut, ChatReply, PaperDetail, PaperListItem, UploadPaperResponse
from .services import (
    build_full_text,
    compute_content_fingerprint,
    extract_pages_from_pdf,
    generate_chat_reply,
    infer_paper_title,
    normalize_title,
    now_iso,
    process_paper,
    update_summary_from_discussion,
)

ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = ROOT / "data" / "uploads"
FRONTEND_DIR = ROOT / "frontend"

app = FastAPI(title="paperReader API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    init_db()


@app.post("/api/papers/upload", response_model=UploadPaperResponse)
async def upload_paper(background_tasks: BackgroundTasks, file: UploadFile = File(...)) -> UploadPaperResponse:
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF file is allowed.")

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    safe_name = f"{timestamp}_{file.filename}"
    save_path = UPLOAD_DIR / safe_name
    content = await file.read()
    save_path.write_bytes(content)

    fallback_title = Path(file.filename).stem
    try:
        pages = extract_pages_from_pdf(save_path)
        full_text = build_full_text(pages)
        title = infer_paper_title(fallback_title, pages)
        canonical_title = normalize_title(title)
        content_fingerprint = compute_content_fingerprint(full_text)
    except Exception:
        title = fallback_title
        canonical_title = normalize_title(title)
        content_fingerprint = ""

    with get_conn() as conn:
        existing = None
        if content_fingerprint:
            existing = conn.execute(
                """
                SELECT id, title, status FROM papers
                WHERE content_fingerprint = ?
                  AND status = 'completed'
                ORDER BY id DESC
                LIMIT 1
                """,
                (content_fingerprint,),
            ).fetchone()
        if not existing and canonical_title:
            existing = conn.execute(
                """
                SELECT id, title, status FROM papers
                WHERE canonical_title = ?
                  AND status = 'completed'
                ORDER BY id DESC
                LIMIT 1
                """,
                (canonical_title,),
            ).fetchone()

        if existing:
            if save_path.exists():
                save_path.unlink(missing_ok=True)
            return UploadPaperResponse(
                id=existing["id"],
                title=existing["title"],
                status=existing["status"],
                duplicate=True,
                duplicate_of=existing["id"],
                message="该论文已处理过，已复用历史结果。",
            )

        cursor = conn.execute(
            """
            INSERT INTO papers (title, canonical_title, content_fingerprint, filename, filepath, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                canonical_title,
                content_fingerprint if content_fingerprint else None,
                file.filename,
                str(save_path),
                "queued",
                now_iso(),
                now_iso(),
            ),
        )
        paper_id = cursor.lastrowid

    background_tasks.add_task(process_paper, paper_id)
    return UploadPaperResponse(
        id=paper_id,
        title=title,
        status="queued",
        duplicate=False,
        duplicate_of=None,
        message="上传成功，已加入解析队列。",
    )


@app.get("/api/papers", response_model=list[PaperListItem])
def list_papers() -> list[PaperListItem]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, title, filename, status, created_at FROM papers ORDER BY id DESC"
        ).fetchall()
    return [
        PaperListItem(
            id=row["id"],
            title=row["title"],
            filename=row["filename"],
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
        for row in rows
    ]


@app.get("/api/papers/{paper_id}", response_model=PaperDetail)
def get_paper(paper_id: int) -> PaperDetail:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Paper not found")
    return PaperDetail(
        id=row["id"],
        title=row["title"],
        filename=row["filename"],
        status=row["status"],
        summary=from_json(row["summary_json"]),
        summary_version=row["summary_version"] or 0,
        summary_updated_at=datetime.fromisoformat(row["summary_updated_at"]) if row["summary_updated_at"] else None,
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


@app.get("/api/papers/{paper_id}/pdf")
def get_paper_pdf(paper_id: int) -> FileResponse:
    with get_conn() as conn:
        row = conn.execute("SELECT filepath, filename FROM papers WHERE id = ?", (paper_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Paper not found")
    safe_filename = row["filename"].replace('"', "")
    return FileResponse(
        path=row["filepath"],
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{safe_filename}"'},
    )


@app.get("/api/papers/{paper_id}/chat", response_model=list[ChatMessageOut])
def get_chat_messages(paper_id: int) -> list[ChatMessageOut]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, role, content, source_hint, created_at FROM messages WHERE paper_id = ? ORDER BY id ASC",
            (paper_id,),
        ).fetchall()
    return [
        ChatMessageOut(
            id=row["id"],
            role=row["role"],
            content=row["content"],
            source_hint=row["source_hint"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
        for row in rows
    ]


@app.post("/api/papers/{paper_id}/chat", response_model=ChatReply)
def chat_with_paper(paper_id: int, req: ChatMessageIn) -> ChatReply:
    with get_conn() as conn:
        paper = conn.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
        if not paper:
            raise HTTPException(status_code=404, detail="Paper not found")

        conn.execute(
            "INSERT INTO messages (paper_id, role, content, source_hint, created_at) VALUES (?, ?, ?, ?, ?)",
            (paper_id, "user", req.message, None, now_iso()),
        )

    answer, hint = generate_chat_reply(paper, req.message)
    if req.update_summary:
        merged_summary, summary_version, summary_updated_at = update_summary_from_discussion(
            paper, req.message, answer, hint
        )
    else:
        merged_summary = from_json(paper["summary_json"])
        summary_version = paper["summary_version"] or 0
        summary_updated_at = paper["summary_updated_at"]
    with get_conn() as conn:
        cursor = conn.execute(
            "INSERT INTO messages (paper_id, role, content, source_hint, created_at) VALUES (?, ?, ?, ?, ?)",
            (paper_id, "assistant", answer, hint, now_iso()),
        )
        msg_id = cursor.lastrowid
        row = conn.execute(
            "SELECT id, role, content, source_hint, created_at FROM messages WHERE id = ?", (msg_id,)
        ).fetchone()

    return ChatReply(
        answer=ChatMessageOut(
            id=row["id"],
            role=row["role"],
            content=row["content"],
            source_hint=row["source_hint"],
            created_at=datetime.fromisoformat(row["created_at"]),
        ),
        summary=merged_summary,
        summary_version=summary_version,
        summary_updated_at=datetime.fromisoformat(summary_updated_at) if summary_updated_at else None,
    )


@app.post("/api/papers/{paper_id}/refresh-summary", response_model=PaperDetail)
def refresh_summary(paper_id: int, background_tasks: BackgroundTasks) -> PaperDetail:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Paper not found")
        conn.execute("UPDATE papers SET status = ?, updated_at = ? WHERE id = ?", ("queued", now_iso(), paper_id))

    background_tasks.add_task(process_paper, paper_id)
    return get_paper(paper_id)


@app.delete("/api/papers/{paper_id}")
def delete_paper(paper_id: int) -> dict[str, int | str]:
    with get_conn() as conn:
        row = conn.execute("SELECT filepath FROM papers WHERE id = ?", (paper_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Paper not found")

        conn.execute("DELETE FROM messages WHERE paper_id = ?", (paper_id,))
        conn.execute("DELETE FROM chunks WHERE paper_id = ?", (paper_id,))
        conn.execute("DELETE FROM papers WHERE id = ?", (paper_id,))

    file_path = Path(row["filepath"])
    if file_path.exists():
        file_path.unlink(missing_ok=True)

    return {"deleted_id": paper_id, "message": "Paper deleted"}


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
