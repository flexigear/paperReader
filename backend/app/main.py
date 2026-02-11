from datetime import datetime
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .db import from_json, get_conn, init_db
from .schemas import ChatMessageIn, ChatMessageOut, ChatReply, PaperDetail, PaperListItem, UploadPaperResponse
from .services import generate_chat_reply, now_iso, process_paper

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

    title = Path(file.filename).stem
    with get_conn() as conn:
        cursor = conn.execute(
            """
            INSERT INTO papers (title, filename, filepath, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (title, file.filename, str(save_path), "queued", now_iso(), now_iso()),
        )
        paper_id = cursor.lastrowid

    background_tasks.add_task(process_paper, paper_id)
    return UploadPaperResponse(id=paper_id, title=title, status="queued")


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
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


@app.get("/api/papers/{paper_id}/pdf")
def get_paper_pdf(paper_id: int) -> FileResponse:
    with get_conn() as conn:
        row = conn.execute("SELECT filepath, filename FROM papers WHERE id = ?", (paper_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Paper not found")
    return FileResponse(path=row["filepath"], media_type="application/pdf", filename=row["filename"])


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
        )
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


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
