# Brain Document Schema

Every document ingested by `brain` must be a **Markdown file with YAML frontmatter**. This schema makes parsing deterministic and enables rich metadata filtering when querying.

## Required Fields

| Field | Type | Description |
|---|---|---|
| `title` | string | Document title |
| `date` | date (ISO 8601) | Document date, e.g. `2026-04-26` |
| `type` | enum | One of: `note`, `meeting`, `article`, `book`, `journal` |

## Optional Fields

| Field | Type | Description |
|---|---|---|
| `tags` | list of strings | Categories or labels, e.g. `[sales, acme]` |
| `author` | string | Who wrote or generated the document |
| `source` | string | Origin, e.g. `zoom-transcript`, `manual`, `slack-export` |

These fields are stored on every chunk so answers can cite the original note, date, document type, source path, and markdown section.

## Example: Meeting Notes

```markdown
---
title: Sales Meeting with Acme Corp
date: 2026-04-26
type: meeting
tags: [sales, acme, q2]
author: Alice Smith
source: zoom-transcript
---

## Opening
Alice: Welcome everyone. Let's review Q2 pipeline.

## Action Items
- Bob to send proposal by Friday
- Carol to schedule follow-up
```

## Example: Journal Entry

```markdown
---
title: Daily Standup Notes
date: 2026-04-26
type: journal
tags: [standup, engineering]
---

Shipped the auth refactor. Blocked on API review.
```

## Validation Rules

- Missing `title`, `date`, or `type` → **rejected** with a clear error
- `type` must be one of the allowed enum values
- `date` must be a valid ISO date (`YYYY-MM-DD`)
- Files without frontmatter delimiters (`---`) are **rejected**

## Retrieval Notes

Brain chunks markdown by heading hierarchy (`#` through `######`) and preserves breadcrumbs such as:

```text
Sales Meeting with Acme Corp > Action Items
```

Use clear headings for better citations. Lists, tables, quotes, and fenced code blocks are kept together where possible. If you change a note and re-run `brain add`, Brain replaces that source's old chunks before storing the new ones, preventing stale answers.

## Raw / Unstructured Text

If you have plain text without frontmatter (e.g. a Google Meet transcript), use the import command:

```bash
brain import raw-transcript.txt \
  --title "Meet with Acme" \
  --date 2026-04-26 \
  --type meeting \
  --tag sales \
  --author "Gemini"
```

This wraps the raw text in valid frontmatter before ingestion.

## Config Reference (`~/.brain/config.toml`)

### LLM Provider Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `provider` | string | `"ollama"` | Driver to use: `"ollama"`, `"litellm"`, or `"openai_compat"` |
| `api_key` | string \| null | `null` | API key for cloud providers. Falls back to env vars (`OPENAI_API_KEY`, etc.) when unset |
| `base_url` | string \| null | `null` | Custom endpoint URL (e.g. OpenRouter, local proxy, LM Studio) |

### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `chat_model` | string | `"gemma4:e4b"` | Model name for chat/generation. Use `provider/model` format for LiteLLM (e.g. `openai/gpt-4o`) |
| `embed_model` | string | `"nomic-embed-text"` | Model name for embeddings |
| `ollama_url` | string | `"http://localhost:11434"` | Ollama server URL (only used when `provider = "ollama"`) |

### Retrieval Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `retrieval_fetch_k` | int | `40` | Candidate chunks fetched from vector DB before re-ranking |
| `retrieval_top_k` | int | `8` | Final chunks sent to the model after MMR selection |
| `retrieval_mmr_lambda` | float | `0.7` | MMR relevance/diversity tradeoff (0 = max diversity, 1 = max relevance) |
| `retrieval_max_context_chars` | int | `12000` | Token budget cap for context passed to the model |
| `retrieval_max_best_distance` | float | `500.0` | Discard all results if the best match exceeds this distance |
| `retrieval_relative_distance_margin` | float | `0.8` | Drop candidates more than this fraction further than the best match |
