# Project State

## Snapshot

- Project: `paperReader`
- Date: `2026-02-11`
- Baseline commit: `0268653` (current branch base)
- Runtime: Debian + Python venv + FastAPI + SQLite

## Completed

- PDF upload from web UI (`UPLOAD` tab), compatible with PC/Android/iPhone browsers.
- Duplicate filtering by normalized content fingerprint + canonical title.
- Async processing pipeline (`queued -> processing -> completed/failed`).
- Multilingual summary in EN/JA/ZH with fixed 3-part semantics:
  - `question`: what problem this paper solves
  - `solution`: paper-proposed method solving that problem
  - `findings`: results obtained through that solution
- `PAPER` tab inline PDF viewing.
- `PAPER` tab paging via server-side single-page PDF endpoint.
- `RESULTS` tab vertical list with paper title + status, open/delete actions.
- `RESULTS` detail panel supports close action.
- Paper chat with retrieved page hints.
- Manual summary controls:
  - `重新总结` (re-run full paper summary)
  - `更新总结` (update summary from latest discussion pair)
- Debian background control scripts:
  - `scripts/paperreader-start.sh`
  - `scripts/paperreader-stop.sh`
  - `scripts/paperreader-status.sh`
  - `scripts/paperreader-restart.sh`

## Current Behavior Notes

- Chat does not auto-update summary by default.
- Summary updates are explicit and user-triggered via button/API.
- App top title is `Paper Reader`.

## Known Risks

- Retrieval is lexical scoring; very long papers can still miss some key context.
- Title extraction is heuristic and may include noise on some PDF layouts.
- No authentication/authorization (single-user local deployment assumption).

## Next Actions

1. Upgrade retrieval with embeddings + reranking.
2. Add optional manual title correction in UI.
3. Add systemd service unit for boot persistence.
4. Add export (Markdown/JSON) for summary + chat transcript.
