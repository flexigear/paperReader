# paper reader

AI paper reader (Web prototype).

## Implemented Features

- Upload PDF papers (PC/Android/iPhone browsers supported).
- Server receives uploads and parses text asynchronously.
- Multilingual summaries in EN/JA/ZH:
  - The problem this paper solves (answer-style description)
  - How the paper solves the problem (answer-style description)
  - Results obtained from the solution (answer-style description)
- Three-tab UI:
  - `UPLOAD`: upload a paper
  - `PAPER`: view the original PDF
  - `RESULTS`: results list + details + AI chat
- PDF paging in the `PAPER` tab (server-side single-page PDF output for mobile compatibility).
- Retrieval-augmented Q&A (RAG):
  - Chunk by page and store in the `chunks` index
  - Retrieve relevant chunks before answering
  - Answers include page citations (e.g. `[Page 7]`)
- Discussion-based summary updates:
  - Each discussion round can be merged into the multilingual summary
  - Summary versioning and last-updated time are recorded
- Upload deduplication:
  - Compare content fingerprint + normalized title
  - Reuse existing results for duplicates (no re-parse)

## Tech Stack

- Backend: FastAPI + SQLite
- PDF parsing: pypdf
- LLM: OpenAI Responses API
- Frontend: vanilla HTML/CSS/JS (mobile responsive)

## Model Defaults

- Summary model: `gpt-5.2-pro`
- Chat model: `gpt-5.2-pro`

Override via environment variables:

- `OPENAI_SUMMARY_MODEL`
- `OPENAI_CHAT_MODEL`

## Quick Start

```bash
cd /mnt/projects/paperReader
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY="<your_api_key>"
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open `http://localhost:8000`.

## CI

Push/PR runs `pytest` automatically and publishes a test report in the Actions Summary.

## Maintenance Notes (Session Handoff)

- Key docs:
  - `docs/PROJECT_STATE.md`: status/risks/next actions
  - `docs/architecture.md`: architecture and data model
  - `docs/API.md`: API reference
  - `docs/WORKLOG.md`: work history and context
- Core implementation:
  - `backend/app/main.py`: API entrypoints and routing
  - `backend/app/services.py`: PDF parsing, retrieval, summaries, chat
  - `frontend/index.html` / `frontend/app.js` / `frontend/styles.css`: UI
  - `tests/test_pdf_paging.py`: PDF paging tests

## Debian Background Scripts

```bash
cd /mnt/projects/paperReader
scripts/paperreader-start.sh     # start in background
scripts/paperreader-status.sh    # check status
scripts/paperreader-restart.sh   # restart service
scripts/paperreader-stop.sh      # stop service
```

Notes:
- Log file: `.run/paper-reader.log`
- PID file: `.run/paper-reader.pid`
- Bind address can be overridden via `HOST` and `PORT`
- `paperreader-start.sh` loads `.env` automatically
- Startup enforces `OPENAI_API_KEY` and aborts if missing

## Directory Layout

- `backend/app/main.py`: API entrypoint + static UI hosting
- `backend/app/services.py`: PDF extraction, chunking, summary generation, chat
- `backend/app/db.py`: SQLite initialization and access
- `frontend/index.html`: three-tab UI
- `frontend/app.js`: frontend interaction logic
- `frontend/styles.css`: styling
- `data/uploads/`: uploaded PDF storage

## Docs Entry

- `docs/PROJECT_STATE.md`: current state, completed items, risks, and next steps
- `docs/architecture.md`: system architecture, flow, data model, constraints
- `docs/API.md`: API reference and examples
- `docs/CHANGELOG.md`: change history
- `docs/WORKLOG.md`: worklog (for session continuity)

## Current Limitations

- No authentication/authorization (single-user local deployment assumption).
- Retrieval is lexical scoring only (can be upgraded to embeddings).
- Summary merging depends on model quality; complex disputes still need manual review.
