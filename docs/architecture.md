# Architecture

## System Overview

- Frontend: static HTML/CSS/JS served by FastAPI.
- Backend: FastAPI REST endpoints + background processing tasks.
- Storage: SQLite (`data/paper_reader.db`) and local PDF files (`data/uploads/`).
- Model: OpenAI Responses API (current runtime target: `gpt-5.2-pro`).
- PDF viewing: server renders single-page PDFs for paging in the PAPER tab.

## Main Flow

1. User uploads a PDF.
2. Backend stores the file and computes:
  - inferred title
  - canonical title
  - content fingerprint
3. Dedup check against existing `completed` papers.
4. If duplicate: return existing paper id and reuse result.
5. If new: create paper row with `queued`, then process in background.
6. Background task extracts page text, chunks text, and builds full text.
7. Model generates EN/JA/ZH summary (question/solution/findings semantics).
8. Paper status becomes `completed` with summary and chunk index.
9. Chat requests retrieve relevant chunks first, then ask model with source hint.
10. Summary update is user-driven:
  - full regenerate via `refresh-summary`
  - discussion-based merge via `update-summary-from-discussion`

## Data Model

### papers

- `id`
- `title`
- `canonical_title`
- `content_fingerprint`
- `filename`
- `filepath`
- `status` (`queued`, `processing`, `completed`, `failed`)
- `summary_json`
- `summary_version`
- `summary_updated_at`
- `full_text`
- `created_at`
- `updated_at`

### chunks

- `id`
- `paper_id`
- `page_start`
- `page_end`
- `content`
- `created_at`

### messages

- `id`
- `paper_id`
- `role` (`user`, `assistant`)
- `content`
- `source_hint`
- `created_at`

## Prompt Policies

- English-first evidence processing.
- Fixed 3-part semantics:
  - `question`: what problem this paper solves
  - `solution`: how the paper solves that problem
  - `findings`: what results are obtained through that solution
- Output in EN/JA/ZH.
- Prefer readable structured plain text (paragraph breaks + short bullets), avoid markdown-heavy formatting.
- If evidence is insufficient, model should state uncertainty explicitly.

## Deployment Shape

- Default run: `uvicorn backend.app.main:app --host 0.0.0.0 --port 8000`
- Scripted background control: `scripts/paperreader-*.sh`
