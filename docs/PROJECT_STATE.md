# Project State

## Snapshot

- Project: `paperReader`
- Date: `2026-02-11`
- Latest commit at snapshot time: `fe0986d`
- Runtime: Debian + Python venv + FastAPI + SQLite

## Completed

- PDF upload from web UI (`UPLOAD` tab).
- Duplicate filtering by normalized content fingerprint + canonical title.
- Async paper processing (queued -> processing -> completed/failed).
- Multilingual summary in EN/JA/ZH with fixed 3-part structure:
  - Problem
  - Solution
  - Result
- `PAPER` tab inline PDF viewing.
- `RESULTS` tab vertical paper list + open/delete actions.
- RAG-style chat: retrieve chunks first, answer with page hints.
- Summary auto-update after each chat turn with versioning fields.
- Debian service scripts:
  - `scripts/paperreader-start.sh`
  - `scripts/paperreader-stop.sh`
  - `scripts/paperreader-status.sh`

## In Progress

- Retrieval is currently lexical scoring (not embeddings yet).

## Known Issues / Risks

- Very long papers still rely on truncation in summarization prompt.
- Title extraction is heuristic and may still fail on some paper layouts.
- No authentication/authorization (single-user local deployment assumption).

## Decisions

- Keep SQLite for early-stage speed and low ops overhead.
- Use English-first evidence policy in prompts, then produce multilingual output.
- Require explicit uncertainty when evidence is insufficient.
- Reuse only `completed` papers for deduplication to avoid empty/partial reuse.

## Next Actions

1. Add embedding-based retrieval for better relevance on long papers.
2. Add optional manual title edit in UI.
3. Add systemd unit for persistent boot-time service.
4. Add export (Markdown/JSON) for summary + chat transcript.
