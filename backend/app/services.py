import io
import json
import os
import re
import sqlite3
from hashlib import sha256
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from pypdf import PdfWriter

from .db import from_json, get_conn, to_json

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None

MODEL_SUMMARY = os.getenv("OPENAI_SUMMARY_MODEL", "gpt-5.2-pro")
MODEL_CHAT = os.getenv("OPENAI_CHAT_MODEL", "gpt-5.2-pro")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


class ServiceError(Exception):
    pass


def _get_openai_client() -> OpenAI:
    if OpenAI is None:
        raise ServiceError("OpenAI SDK is unavailable.")
    if not OPENAI_API_KEY:
        raise ServiceError("OPENAI_API_KEY is missing.")
    return OpenAI(api_key=OPENAI_API_KEY)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def extract_pages_from_pdf(pdf_path: Path) -> list[tuple[int, str]]:
    reader = PdfReader(str(pdf_path))
    pages: list[tuple[int, str]] = []
    for idx, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text = text.replace("\r", "\n")
        text = re.sub(r"[ \t]+", " ", text)
        clean = re.sub(r"\n{3,}", "\n\n", text).strip()
        pages.append((idx, clean))
    return pages


def get_pdf_page_count(pdf_path: Path) -> int:
    reader = PdfReader(str(pdf_path))
    return len(reader.pages)


def render_single_page_pdf(pdf_path: Path, page_no: int) -> bytes:
    reader = PdfReader(str(pdf_path))
    total = len(reader.pages)
    if page_no < 1 or page_no > total:
        raise ValueError("page out of range")
    writer = PdfWriter()
    writer.add_page(reader.pages[page_no - 1])
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def infer_paper_title(fallback_title: str, pages: list[tuple[int, str]]) -> str:
    def _clean_line(raw: str) -> str:
        return re.sub(r"\s+", " ", raw).strip(" -_:\t")

    def _is_author_or_affiliation(line: str) -> bool:
        lower = line.lower()
        bad_markers = [
            "@",
            "university",
            "institute",
            "department",
            "laboratory",
            "school of",
            "college of",
            "arxiv",
            "http://",
            "https://",
            "corresponding author",
        ]
        if any(marker in lower for marker in bad_markers):
            return True
        if re.search(r"\b(and|et al\.?)\b", lower) and len(line) < 120:
            return True
        if line.count(",") >= 2 and len(line.split()) < 16:
            return True
        return False

    def _is_title_like(line: str) -> bool:
        if len(line) < 16 or len(line) > 200:
            return False
        if re.fullmatch(r"[0-9.\- ]+", line):
            return False
        if _is_author_or_affiliation(line):
            return False
        if not re.search(r"[A-Za-z\u4e00-\u9fff\u3040-\u30ff]", line):
            return False
        # Keep lines that look like headline text instead of sentence paragraph.
        if line.count(".") >= 2:
            return False
        return True

    def _safe_title(title: str) -> str:
        lower = title.lower()
        if (title.count(",") >= 2 and len(title.split()) < 20) or lower.count(" and ") >= 2:
            return fallback_title.strip()
        return title

    for _, text in pages[:2]:
        raw_lines = [ln for ln in text.split("\n") if ln.strip()]
        lines = [_clean_line(ln) for ln in raw_lines[:40]]
        lines = [ln for ln in lines if ln]
        for idx, line in enumerate(lines):
            if not _is_title_like(line):
                continue
            if idx + 1 < len(lines):
                next_line = lines[idx + 1]
                if (
                    _is_title_like(next_line)
                    and not _is_author_or_affiliation(next_line)
                    and len(line) + len(next_line) <= 200
                    and not line.endswith((".", "?", "!", ":"))
                ):
                    return _safe_title(f"{line} {next_line}")
            return _safe_title(line)
    return fallback_title.strip()


def normalize_title(title: str) -> str:
    lowered = title.lower().strip()
    normalized = re.sub(r"[^a-z0-9\u4e00-\u9fff\u3040-\u30ff]+", " ", lowered)
    return re.sub(r"\s+", " ", normalized).strip()


def compute_content_fingerprint(full_text: str) -> str:
    normalized = re.sub(r"[^a-z0-9\u4e00-\u9fff\u3040-\u30ff]+", "", full_text.lower())
    if len(normalized) > 500000:
        normalized = normalized[:500000]
    return sha256(normalized.encode("utf-8")).hexdigest()


def build_full_text(pages: Iterable[tuple[int, str]]) -> str:
    parts: list[str] = []
    for page_no, text in pages:
        parts.append(f"[Page {page_no}]\n{text}")
    return "\n\n".join(parts).strip()


def parse_pages_from_full_text(full_text: str) -> list[tuple[int, str]]:
    matches = list(re.finditer(r"\[Page (\d+)\]\n", full_text))
    if not matches:
        text = re.sub(r"\s+", " ", full_text).strip()
        return [(1, text)] if text else []

    pages: list[tuple[int, str]] = []
    for idx, match in enumerate(matches):
        page_no = int(match.group(1))
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(full_text)
        content = re.sub(r"\s+", " ", full_text[start:end]).strip()
        pages.append((page_no, content))
    return pages


def _slice_text(text: str, max_chars: int, overlap: int) -> list[str]:
    if not text:
        return []

    if overlap >= max_chars:
        overlap = max_chars // 4

    slices: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        chunk = text[start:end].strip()
        if chunk:
            slices.append(chunk)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return slices


def build_chunks(pages: list[tuple[int, str]]) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for page_no, text in pages:
        if not text:
            continue
        for piece in _slice_text(text, max_chars=1400, overlap=220):
            chunks.append(
                {
                    "page_start": page_no,
                    "page_end": page_no,
                    "content": piece,
                }
            )
    return chunks


def _trim_text(text: str, max_chars: int = 120000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars]


def _empty_summary() -> dict[str, Any]:
    return {
        "zh": {"question": "", "solution": "", "findings": ""},
        "en": {"question": "", "solution": "", "findings": ""},
        "ja": {"question": "", "solution": "", "findings": ""},
    }


def _normalize_summary_shape(summary: dict[str, Any] | None, title: str) -> dict[str, Any]:
    _ = title
    base = _empty_summary()
    incoming = summary or {}
    for lang in ("zh", "en", "ja"):
        src = incoming.get(lang, {})
        for field in ("question", "solution", "findings"):
            value = src.get(field) if isinstance(src, dict) else None
            if isinstance(value, str) and value.strip():
                base[lang][field] = value.strip()
    return base


def _assert_summary_complete(summary: dict[str, Any]) -> None:
    for lang in ("zh", "en", "ja"):
        block = summary.get(lang, {})
        if not isinstance(block, dict):
            raise ServiceError(f"Summary format invalid for language: {lang}")
        for field in ("question", "solution", "findings"):
            value = block.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ServiceError(f"Summary field missing or empty: {lang}.{field}")


def _parse_json_from_text(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(text[start : end + 1])
    raise ServiceError("Model response did not contain valid JSON.")


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]{1,2}|[\u3040-\u30ff]{1,2}", text.lower())
    return [t for t in tokens if len(t.strip()) > 0]


def retrieve_relevant_chunks(paper_id: int, query: str, limit: int = 6) -> list[sqlite3.Row]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, page_start, page_end, content FROM chunks WHERE paper_id = ?",
            (paper_id,),
        ).fetchall()
        if not rows:
            paper = conn.execute("SELECT full_text FROM papers WHERE id = ?", (paper_id,)).fetchone()
            full_text = paper["full_text"] if paper else None
            if full_text:
                pages = parse_pages_from_full_text(full_text)
                chunks = build_chunks(pages)
                _replace_chunks(conn, paper_id, chunks)
                rows = conn.execute(
                    "SELECT id, page_start, page_end, content FROM chunks WHERE paper_id = ?",
                    (paper_id,),
                ).fetchall()

    if not rows:
        return []

    query_lower = query.lower().strip()
    q_tokens = _tokenize(query)
    scored: list[tuple[float, sqlite3.Row]] = []

    for row in rows:
        content = row["content"].lower()
        score = 0.0

        if query_lower and query_lower in content:
            score += 8.0

        for token in q_tokens:
            count = content.count(token)
            if count:
                score += 1.0 + min(count, 3) * 0.9

        if score == 0 and query_lower:
            overlap = len(set(query_lower) & set(content))
            score += overlap * 0.04

        scored.append((score, row))

    scored.sort(key=lambda item: (-item[0], item[1]["page_start"], item[1]["id"]))

    if scored[0][0] <= 0:
        fallback = sorted(rows, key=lambda r: (r["page_start"], r["id"]))
        return fallback[:limit]
    return [row for _, row in scored[:limit]]


def format_source_hint(chunks: list[sqlite3.Row]) -> str:
    if not chunks:
        return "No source chunk retrieved"

    refs: list[str] = []
    for chunk in chunks:
        if chunk["page_start"] == chunk["page_end"]:
            refs.append(f"Page {chunk['page_start']}")
        else:
            refs.append(f"Page {chunk['page_start']}-{chunk['page_end']}")

    unique_refs = list(dict.fromkeys(refs))
    return "Retrieved context: " + ", ".join(unique_refs)


def _render_context(chunks: list[sqlite3.Row]) -> str:
    if not chunks:
        return "(No chunk context available)"

    context_parts: list[str] = []
    for idx, chunk in enumerate(chunks, start=1):
        context_parts.append(
            f"[Chunk {idx} | Page {chunk['page_start']}-{chunk['page_end']}]\n{chunk['content']}"
        )
    return "\n\n".join(context_parts)


def summarize_paper(title: str, full_text: str) -> dict[str, Any]:
    client = _get_openai_client()
    prompt = (
        "You are an expert research paper reader. Return JSON only with keys zh, en, ja. "
        "Use English source content as the primary basis for understanding and reasoning first, "
        "then produce multilingual outputs. "
        "If evidence is insufficient, state uncertainty explicitly instead of guessing. "
        "Each language object must include: question, solution, findings. "
        "'question' must directly answer: 'What problem does this paper aim to solve?'. "
        "This is a problem statement answer, NOT an interrogative sentence. "
        "In Chinese output, this field should read like the answer to '本论文要解决的问题是什么'. "
        "'solution' must explain the paper's concrete method for solving the problem summarized in 'question'. "
        "This must come from deep reading of the paper content (method/model/objective/training/inference), "
        "not generic advice. "
        "'findings' must answer: based on the solution in 'solution', what results were obtained "
        "(metrics, gains, ablations, qualitative outcomes, limitations). "
        "It must be evidence-grounded and answer-style, not a vague statement. "
        "Formatting rules for each field (question/solution/findings): "
        "produce well-structured plain text with clear paragraph breaks. "
        "Prefer this layout: one short topic sentence, then 2-5 bullet lines. "
        "Keep all important paper details; do NOT over-compress or drop key information. "
        "Avoid markdown symbols such as ## or **. "
        "Do not output question sentences like 'What is ...?'; output declarative answers only.\n\n"
        f"Paper title: {title}\n\n"
        "Paper content:\n"
        f"{_trim_text(full_text)}"
    )

    response = client.responses.create(model=MODEL_SUMMARY, input=prompt)
    data = _parse_json_from_text(response.output_text)
    normalized = _normalize_summary_shape(data, title)
    _assert_summary_complete(normalized)
    return normalized


def generate_chat_reply(paper: sqlite3.Row, user_message: str) -> tuple[str, str | None]:
    summary = from_json(paper["summary_json"]) or {}
    chunks = retrieve_relevant_chunks(paper["id"], user_message, limit=6)
    source_hint = format_source_hint(chunks)
    client = _get_openai_client()
    prompt = (
        "You are a research assistant for scientific papers. "
        "Use English source content as the primary basis for understanding and reasoning first. "
        "Answer in Chinese by default unless user asks other language. "
        "Use only the retrieved chunks as evidence. "
        "When answering, cite evidence with [Page X] or [Page X-Y]. "
        "If evidence is insufficient, explicitly say uncertain and identify missing evidence.\n\n"
        "Output format rules:\n"
        "1) Return plain text only (no markdown symbols like ##, **, or tables).\n"
        "2) Use clear line breaks and short paragraphs.\n"
        "3) Use this section structure exactly:\n"
        "结论：...\n"
        "依据：- ...\n"
        "细节：- ...\n"
        "不确定性：...\n"
        "4) Keep each bullet concise and evidence-linked.\n\n"
        f"Paper title: {paper['title']}\n"
        f"Current summary JSON: {json.dumps(summary, ensure_ascii=False)}\n\n"
        "Retrieved evidence chunks:\n"
        f"{_render_context(chunks)}\n\n"
        f"User question: {user_message}"
    )

    response = client.responses.create(model=MODEL_CHAT, input=prompt)
    answer = response.output_text.strip()
    return answer, source_hint


def update_summary_from_discussion(
    paper: sqlite3.Row, user_message: str, assistant_answer: str, source_hint: str | None
) -> tuple[dict[str, Any], int, str]:
    current_summary = _normalize_summary_shape(from_json(paper["summary_json"]), paper["title"])
    now = now_iso()
    client = _get_openai_client()
    prompt = (
        "You are updating an existing multilingual paper summary after a user discussion. "
        "Use English source content as the primary basis for understanding and reasoning first, "
        "then update multilingual outputs. "
        "If evidence is insufficient, keep uncertainty explicit and do not fabricate details. "
        "Return JSON only with keys zh, en, ja; each has question, solution, findings. "
        "'question' must remain the direct answer to 'What problem does this paper aim to solve?' "
        "(Chinese meaning: '本论文要解决的问题是什么'). "
        "It must be declarative, never a question sentence. "
        "'solution' must remain tightly aligned to that 'question': "
        "it is the paper-proposed method to solve the summarized target problem, based on paper evidence. "
        "'findings' must remain aligned to 'solution': "
        "it states what results were obtained through that solution, based on paper evidence. "
        "Formatting rules: each field should be readable plain text with paragraph breaks, "
        "prefer one topic sentence + 2-5 bullet lines. "
        "Keep important details; do not drop information for brevity. "
        "Avoid markdown symbols like ## or **. "
        "Integrate only reliable new insights supported by assistant answer and source hint. "
        "Keep prior good points and refine wording if needed.\n\n"
        f"Paper title: {paper['title']}\n"
        f"Current summary JSON: {json.dumps(current_summary, ensure_ascii=False)}\n"
        f"User message: {user_message}\n"
        f"Assistant answer: {assistant_answer}\n"
        f"Source hint: {source_hint or 'N/A'}\n"
    )
    response = client.responses.create(model=MODEL_SUMMARY, input=prompt)
    parsed = _parse_json_from_text(response.output_text)
    merged = _normalize_summary_shape(parsed, paper["title"])
    _assert_summary_complete(merged)

    with get_conn() as conn:
        conn.execute(
            """
            UPDATE papers
            SET summary_json = ?,
                summary_version = COALESCE(summary_version, 0) + 1,
                summary_updated_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (to_json(merged), now, now, paper["id"]),
        )
        row = conn.execute(
            "SELECT summary_version, summary_updated_at FROM papers WHERE id = ?",
            (paper["id"],),
        ).fetchone()

    return merged, row["summary_version"], row["summary_updated_at"]


def _replace_chunks(conn: sqlite3.Connection, paper_id: int, chunks: list[dict[str, Any]]) -> None:
    conn.execute("DELETE FROM chunks WHERE paper_id = ?", (paper_id,))
    for chunk in chunks:
        conn.execute(
            """
            INSERT INTO chunks (paper_id, page_start, page_end, content, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (paper_id, chunk["page_start"], chunk["page_end"], chunk["content"], now_iso()),
        )


def process_paper(paper_id: int) -> None:
    with get_conn() as conn:
        paper = conn.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
        if not paper:
            return
        conn.execute(
            "UPDATE papers SET status = ?, updated_at = ? WHERE id = ?",
            ("processing", now_iso(), paper_id),
        )

    try:
        pages = extract_pages_from_pdf(Path(paper["filepath"]))
        full_text = build_full_text(pages)
        canonical_title = normalize_title(infer_paper_title(paper["title"], pages))
        fingerprint = compute_content_fingerprint(full_text)
        chunks = build_chunks(pages)
        summary = summarize_paper(paper["title"], full_text)

        with get_conn() as conn:
            _replace_chunks(conn, paper_id, chunks)
            conn.execute(
                """
                UPDATE papers
                SET status = ?,
                    full_text = ?,
                    canonical_title = ?,
                    content_fingerprint = ?,
                    summary_json = ?,
                    summary_version = COALESCE(summary_version, 0) + 1,
                    summary_updated_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                ("completed", full_text, canonical_title, fingerprint, to_json(summary), now_iso(), now_iso(), paper_id),
            )
    except Exception as exc:  # pragma: no cover
        with get_conn() as conn:
            conn.execute(
                "UPDATE papers SET status = ?, updated_at = ?, summary_json = ? WHERE id = ?",
                ("failed", now_iso(), to_json({"error": str(exc)}), paper_id),
            )
