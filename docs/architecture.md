# Architecture

## System Overview

- Frontend: static HTML/CSS/JS served by FastAPI.
- Backend: FastAPI REST endpoints + background processing tasks.
- Storage: SQLite (`data/paper_reader.db`) and local PDF files (`data/uploads/`).
- Model: OpenAI Responses API (`gpt-5.2-pro` by default).

## Main Flow

1. User uploads a PDF.
2. Backend stores the file and computes:
  - inferred title
  - canonical title
  - content fingerprint
3. Dedup check against existing `completed` papers.
4. If duplicate: return existing paper id.
5. If new: create paper row with `queued`, then process in background.
6. Background task extracts page text, chunks text, builds full text.
7. Model generates EN/JA/ZH summary (Problem/Solution/Result).
8. Paper status becomes `completed` with summary and chunk index.
9. Chat requests retrieve relevant chunks first, then ask model.
10. After each chat response, summary is updated and summary version increments.

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
- 3-part summary semantics:
  - `question`: direct answer to "what problem this paper solves"
  - `solution`: paper-proposed method solving that problem
  - `findings`: results obtained from that solution
- If evidence is insufficient, model must explicitly state uncertainty.

## Deployment Shape

- Default run: `uvicorn backend.app.main:app --host 0.0.0.0 --port 8000`
- Scripted background control: `scripts/paperreader-*.sh`
