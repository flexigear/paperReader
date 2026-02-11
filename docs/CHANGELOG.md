# Changelog

## 2026-02-11

- Bootstrapped repository and MVP web app (FastAPI + static frontend).
- Added upload, parsing queue, PDF viewer, multilingual summary, and chat.
- Added deduplication using content fingerprint + canonical title.
- Added paper delete endpoint and UI action.
- Standardized summary semantics to:
  - Problem solved by this paper
  - Solution
  - Results
- Added explicit manual summary update flow:
  - `POST /api/papers/{paper_id}/refresh-summary`
  - `POST /api/papers/{paper_id}/update-summary-from-discussion`
- Refined model prompt to output more readable structured plain text directly (paragraphs + short bullets).
- Simplified frontend summary formatter to preserve model output content and only normalize line breaks.
- Updated app title display to `Paper Reader`.
- Added project control scripts with `paperreader-` prefix (`start/stop/status/restart`).
