# API Reference

Base URL: `http://<host>:8000`

## POST /api/papers/upload

Upload a paper PDF.

- Content-Type: `multipart/form-data`
- Field: `file` (PDF)

Response (new):

```json
{
  "id": 12,
  "title": "Paper Title",
  "status": "queued",
  "duplicate": false,
  "duplicate_of": null,
  "message": "Upload accepted and queued for parsing."
}
```

Response (duplicate reused):

```json
{
  "id": 7,
  "title": "Existing Paper",
  "status": "completed",
  "duplicate": true,
  "duplicate_of": 7,
  "message": "This paper was already processed; previous results reused."
}
```

## GET /api/papers

List papers.

## GET /api/papers/{paper_id}

Get paper detail, including summary and summary version metadata.

Response includes:

- `page_count`: total PDF pages (if readable).

## GET /api/papers/{paper_id}/pdf

Return PDF content for inline rendering.

## GET /api/papers/{paper_id}/pdf/page/{page_no}

Return a single-page PDF (used for paging in the PAPER tab).

## GET /api/papers/{paper_id}/chat

Get chat history for paper.

## POST /api/papers/{paper_id}/chat

Send a chat message and receive assistant reply.

Request:

```json
{
  "message": "What is the core innovation of this method?",
  "update_summary": false
}
```

Notes:

- `update_summary` is optional and defaults to `false`.
- Recommended flow is manual summary update via dedicated endpoint/button.

Response:

```json
{
  "answer": {
    "id": 100,
    "role": "assistant",
    "content": "...",
    "source_hint": "Retrieved context: Page 3, Page 5",
    "created_at": "2026-02-11T10:00:00+00:00"
  },
  "summary": { "zh": {}, "en": {}, "ja": {} },
  "summary_version": 4,
  "summary_updated_at": "2026-02-11T10:00:00+00:00"
}
```

## POST /api/papers/{paper_id}/refresh-summary

Requeue full summary regeneration for a paper.

## POST /api/papers/{paper_id}/update-summary-from-discussion

Update summary based on latest complete user+assistant discussion pair.

## DELETE /api/papers/{paper_id}

Delete paper, related chunks/messages, and local PDF file.

Response:

```json
{ "deleted_id": 12, "message": "Paper deleted" }
```

## Common Errors

- `400`: invalid upload format (non-PDF)
- `400`: no complete discussion pair found for summary update
- `404`: paper not found
