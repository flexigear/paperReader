# Architecture

## Workflow

1. User uploads a paper PDF in `UPLOAD` tab.
2. Backend stores file in `data/uploads/` and creates a `papers` row with `queued` status.
3. Background task extracts PDF text and asks model for multilingual summary.
4. Status becomes `completed` with stored summary and full text.
5. `RESULTS` tab lists papers; clicking one opens summary + chat.
6. Chat endpoint answers based on paper text and asks model to provide page hints.

## Data Tables

### papers

- `id`
- `title`
- `filename`
- `filepath`
- `status` (`queued`, `processing`, `completed`, `failed`)
- `summary_json`
- `full_text`
- `created_at`
- `updated_at`

### messages

- `id`
- `paper_id`
- `role` (`user`, `assistant`)
- `content`
- `source_hint`
- `created_at`

## Key APIs

- `POST /api/papers/upload`
- `GET /api/papers`
- `GET /api/papers/{paper_id}`
- `GET /api/papers/{paper_id}/pdf`
- `GET /api/papers/{paper_id}/chat`
- `POST /api/papers/{paper_id}/chat`
- `POST /api/papers/{paper_id}/refresh-summary`
