import json
import os
import sqlite3
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


def extract_text_from_pdf(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    parts: list[str] = []
    for idx, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        parts.append(f"\n\n[Page {idx}]\n{text}")
    return "".join(parts).strip()


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
    full_text = paper["full_text"] or ""
    summary = from_json(paper["summary_json"]) or {}

    if not OPENAI_API_KEY or OpenAI is None:
        answer = "当前未配置模型。请先设置 OPENAI_API_KEY 以启用深度问答。"
        hint = "No model configured"
        return answer, hint

    client = OpenAI(api_key=OPENAI_API_KEY)
    prompt = (
        "You are a research assistant. Answer in Chinese by default unless user asks other language. "
        "When possible, include source location like [Page X]. If unsure, say uncertain.\n\n"
        f"Paper title: {paper['title']}\n"
        f"Current summary JSON: {json.dumps(summary, ensure_ascii=False)}\n\n"
        f"Paper text:\n{_trim_text(full_text, max_chars=100000)}\n\n"
        f"User question: {user_message}"
    )

    response = client.responses.create(model=MODEL_CHAT, input=prompt)
    answer = response.output_text.strip()
    hint = "See inline [Page X] citations from the assistant answer."
    return answer, hint


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
        text = extract_text_from_pdf(Path(paper["filepath"]))
        summary = summarize_paper(paper["title"], text)
        with get_conn() as conn:
            conn.execute(
                "UPDATE papers SET status = ?, full_text = ?, summary_json = ?, updated_at = ? WHERE id = ?",
                ("completed", text, to_json(summary), now_iso(), paper_id),
            )
    except Exception as exc:  # pragma: no cover
        with get_conn() as conn:
            conn.execute(
                "UPDATE papers SET status = ?, updated_at = ?, summary_json = ? WHERE id = ?",
                ("failed", now_iso(), to_json({"error": str(exc)}), paper_id),
            )
