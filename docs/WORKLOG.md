# Worklog

## 2026-02-11

- Goal: stabilize paper reading loop for real usage on Debian VM.
- Key result: upload -> parse -> summarize -> discuss -> optional summary update is now a clear manual workflow.
- UI result: title and summary rendering aligned with readability requirements (EN/JA/ZH sections keep model structure).
- Ops result: project-specific background scripts finalized (`paperreader-*`).
- UI fix: server-side PDF paging works across browsers; results detail now closable.
- Maintenance: CI enabled with caching + JUnit report + artifact upload; README updated with maintenance entrypoints.
- Remaining gap: retrieval quality on long papers (embeddings not yet enabled).
