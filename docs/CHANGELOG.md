# Changelog

## 2026-02-11

- Bootstrapped repository and project skeleton.
- Built MVP with FastAPI backend and 3-tab frontend UI.
- Added PDF upload, parsing pipeline, multilingual summary, chat.
- Added RAG-style chunk retrieval and source hints.
- Added summary auto-update after each chat turn.
- Added deduplication via content fingerprint + canonical title.
- Added paper deletion endpoint and UI delete action.
- Improved title extraction heuristics.
- Enforced summary semantics: Problem / Solution / Result.
- Enforced English-first evidence and explicit uncertainty rule.
- Switched default models to `gpt-5.2-pro`.
- Added Debian background control scripts with `paperreader-` prefix.
