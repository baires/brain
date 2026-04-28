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
