# Architecture

## Workflow

1. User uploads a paper PDF in `UPLOAD` tab.
2. Backend stores file in `data/uploads/` and creates a `papers` row with `queued` status.
3. Background task extracts PDF text page-by-page.
4. Backend builds chunk index (`chunks` table) with page mapping.
5. Backend asks model for multilingual summary and stores result.
6. `RESULTS` tab lists papers; clicking one opens summary + chat.
7. For each chat question, backend retrieves top relevant chunks first, then asks model to answer with citations (`[Page X]`).

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

## Retrieval Strategy

- Chunking: split each page into overlapping text windows.
- Ranking: lexical overlap scoring between query and chunk content.
- Context window: top-k chunks are passed to model as evidence.
- Citation: assistant is prompted to cite source pages in final answer.

## Key APIs

- `POST /api/papers/upload`
- `GET /api/papers`
- `GET /api/papers/{paper_id}`
- `GET /api/papers/{paper_id}/pdf`
- `GET /api/papers/{paper_id}/chat`
- `POST /api/papers/{paper_id}/chat`
- `POST /api/papers/{paper_id}/refresh-summary`
