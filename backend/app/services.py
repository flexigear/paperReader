import json
import os
import re
import sqlite3
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from .db import from_json, get_conn, to_json

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None

MODEL_SUMMARY = os.getenv("OPENAI_SUMMARY_MODEL", "gpt-4.1")
MODEL_CHAT = os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


class ServiceError(Exception):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def extract_pages_from_pdf(pdf_path: Path) -> list[tuple[int, str]]:
    reader = PdfReader(str(pdf_path))
    pages: list[tuple[int, str]] = []
    for idx, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        clean = re.sub(r"\s+", " ", text).strip()
        pages.append((idx, clean))
    return pages


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


def _default_summary(title: str) -> dict[str, Any]:
    return {
        "zh": {
            "question": f"论文《{title}》要解决的问题尚待模型深入分析。",
            "solution": "系统已提取论文内容，但当前未配置可用模型。",
            "findings": "请配置 OPENAI_API_KEY 后重试，以获取高质量总结。",
        },
        "en": {
            "question": f"The exact research question in '{title}' needs model analysis.",
            "solution": "Paper text has been extracted, but no model is configured.",
            "findings": "Set OPENAI_API_KEY and re-run for deep summary.",
        },
        "ja": {
            "question": f"論文『{title}』の研究課題はモデル解析が必要です。",
            "solution": "本文抽出は完了しましたが、利用可能なモデルが未設定です。",
            "findings": "高品質な要約を得るには OPENAI_API_KEY を設定してください。",
        },
    }


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
    if not OPENAI_API_KEY or OpenAI is None:
        return _default_summary(title)

    client = OpenAI(api_key=OPENAI_API_KEY)
    prompt = (
        "You are an expert research paper reader. Return JSON only with keys zh, en, ja. "
        "Each language object must include: question, solution, findings. "
        "Use concise but deep explanation.\n\n"
        f"Paper title: {title}\n\n"
        "Paper content:\n"
        f"{_trim_text(full_text)}"
    )

    response = client.responses.create(model=MODEL_SUMMARY, input=prompt)
    data = _parse_json_from_text(response.output_text)

    required = {"zh", "en", "ja"}
    if not required.issubset(set(data.keys())):
        raise ServiceError("Model summary format is invalid.")
    return data


def generate_chat_reply(paper: sqlite3.Row, user_message: str) -> tuple[str, str | None]:
    summary = from_json(paper["summary_json"]) or {}
    chunks = retrieve_relevant_chunks(paper["id"], user_message, limit=6)
    source_hint = format_source_hint(chunks)

    if not OPENAI_API_KEY or OpenAI is None:
        if chunks:
            preview = chunks[0]["content"][:260]
            answer = (
                "当前未配置模型，已返回最相关片段。\n"
                f"定位：{source_hint}\n"
                f"片段预览：{preview}"
            )
        else:
            answer = "当前未配置模型，且暂无可检索片段。请先上传并解析论文。"
        return answer, source_hint

    client = OpenAI(api_key=OPENAI_API_KEY)
    prompt = (
        "You are a research assistant for scientific papers. "
        "Answer in Chinese by default unless user asks other language. "
        "Use only the retrieved chunks as evidence. "
        "When answering, cite evidence with [Page X] or [Page X-Y]. "
        "If evidence is insufficient, explicitly say uncertain.\n\n"
        f"Paper title: {paper['title']}\n"
        f"Current summary JSON: {json.dumps(summary, ensure_ascii=False)}\n\n"
        "Retrieved evidence chunks:\n"
        f"{_render_context(chunks)}\n\n"
        f"User question: {user_message}"
    )

    response = client.responses.create(model=MODEL_CHAT, input=prompt)
    answer = response.output_text.strip()
    return answer, source_hint


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
        chunks = build_chunks(pages)
        summary = summarize_paper(paper["title"], full_text)

        with get_conn() as conn:
            _replace_chunks(conn, paper_id, chunks)
            conn.execute(
                "UPDATE papers SET status = ?, full_text = ?, summary_json = ?, updated_at = ? WHERE id = ?",
                ("completed", full_text, to_json(summary), now_iso(), paper_id),
            )
    except Exception as exc:  # pragma: no cover
        with get_conn() as conn:
            conn.execute(
                "UPDATE papers SET status = ?, updated_at = ?, summary_json = ? WHERE id = ?",
                ("failed", now_iso(), to_json({"error": str(exc)}), paper_id),
            )
