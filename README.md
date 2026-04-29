# Brain — Offline Second Brain

A fully offline CLI tool that ingests documents into a local vector store and answers questions via RAG using local LLMs.

Chat startup                                       |  Chat
:-------------------------------------------------:|:-------------------------:
![Chat startup](/assets/1.png "Chat startup")      |  ![Chat](/assets/2.png "Chat")

```bash
brain add ./notes/
brain ask "what did we discuss in the sales meeting yesterday?"
```

## Requirements

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/)
- [Ollama](https://ollama.com) running locally

## Install

### Option A — Global install (recommended)

Installs `brain` onto your PATH so you can run it from anywhere.

```bash
# Install globally as a uv tool from the public repo
uv tool install git+https://github.com/baires/brain.git

# Pull the models
ollama pull gemma4:e4b
ollama pull nomic-embed-text
```

Update later with:

```bash
uv tool upgrade brain
```

### Option B — Local development install

Keeps everything inside the project folder.

```bash
# Clone or copy this directory
cd brain

# Sync dependencies (creates .venv automatically)
uv sync

# Pull the models
ollama pull gemma4:e4b
ollama pull nomic-embed-text
```

Then either **activate the virtual environment** before each session:

```bash
source .venv/bin/activate
brain init
```

Or prefix every command with `uv run`:

```bash
uv run brain init
uv run brain add ./notes/
```

## Quickstart

```bash
# Initialize config and database
brain init

# Ingest a folder of markdown files
brain add ~/Documents/notes/

# Ask a question
brain ask "what were last week's action items?"

# Filter by document type or date range
brain ask "sales updates" --type meeting --last 7

# Inspect retrieved context behind an answer
brain ask "what did Bob promise Acme?" --show-context

# Interactive chat session (TUI with markdown rendering, memory, RAG)
brain chat

# Watch a folder for new files
brain watch ~/Documents/notes/

# Import raw unstructured text
brain import transcript.txt \
  --title "Team Sync" \
  --date 2026-04-26 \
  --type meeting

# Add a remote and sync from it
brain remote add work my-bucket https://s3.amazonaws.com --prefix notes/ --key-id AKIA... --secret ...
brain sync work

# Check status
brain status

# Optional local-model smoke eval using the demo notes
brain eval notes-demo/ --run-ollama
```

## Document Schema

All ingested files must be **Markdown with YAML frontmatter**. See [`docs/SCHEMA.md`](docs/SCHEMA.md) for the full spec.

Minimal example:

```markdown
---
title: Sales Meeting
date: 2026-04-26
type: meeting
---

Notes go here...
```

## Configuration

Config lives at `~/.brain/config.toml`:

```toml
ollama_url = "http://localhost:11434"
chat_model = "gemma4:e4b"
embed_model = "nomic-embed-text"
db_path = "/Users/you/.brain/brain.db"
chunk_size = 512
chunk_overlap = 50
retrieval_fetch_k = 40
retrieval_top_k = 8
retrieval_mmr_lambda = 0.7
retrieval_max_context_chars = 12000
retrieval_max_best_distance = 500.0
retrieval_relative_distance_margin = 0.8

[agent]
system_prompt = "You are a precise local-notes assistant. Answer using only the provided context. If the context does not answer the question, say: I don't know based on your notes. Always cite sources for factual claims using the citation number and source file path, for example [1: notes/meeting.md]."
tone = "helpful and concise"
goals = "Help the user retrieve information from their knowledge base"
```

## Answers & Citations

Brain is precision-first by default. It retrieves more candidates than it uses, filters weak matches, diversifies near-duplicate chunks, and sends only the strongest context to the local model.

Answers should cite retrieved notes with numbered citations and file paths like `[1: notes/meeting.md]`. Use `--show-context` to see selected chunks, distances, source paths, dates, document types, and section breadcrumbs.

If no retrieved chunk is strong enough, Brain answers:

```text
I don't know based on your notes.
```

After upgrading from an older index, re-run `brain add <notes-dir>` so chunks are rebuilt with richer metadata.

## Chat

`brain chat` opens a full terminal UI for interactive conversations.

**Features:**
- **Markdown rendering** — bold, lists, code blocks, quotes rendered properly
- **Session memory** — follow-up questions work naturally (ephemeral, not persisted)
- **RAG integration** — every message searches your knowledge base automatically
- **Thinking indicator** — "_Thinking..._" placeholder while the LLM processes

**In-chat commands:**
```
/quit     — Exit
/clear    — Clear history
/rag on   — Enable document retrieval (default)
/rag off  — Disable document retrieval
/context  — Show citations used for the last answer
/help     — Show commands
```

## Routines

Automate actions against your brain data: scheduled email digests, Slack alerts on backup, PDF exports, shell commands, and more. Routines are configured in `~/.brain/config.toml` and can be triggered on a schedule, by events, or manually.

```bash
# Run a routine now
brain routine run morning-summary

# Start the scheduler daemon
brain routine daemon

# List configured routines
brain routine list
```

See [`docs/routines.md`](docs/routines.md) for the full guide: built-in actions, trigger types, retry behavior, and how to write your own plugins.

## Cloud Storage Remotes

Brain supports any S3-compatible storage provider via named remotes. Credentials are stored in your OS keyring — never in config files.

```bash
# AWS S3
brain remote add work my-bucket https://s3.amazonaws.com \
  --prefix notes/ \
  --key-id AKIAIOSFODNN7 \
  --secret wJalrXUtnFEMI

# Cloudflare R2
brain remote add r2 my-r2-bucket https://<account>.r2.cloudflarestorage.com \
  --key-id ... --secret ...

# MinIO / self-hosted
brain remote add local my-bucket http://localhost:9000 \
  --key-id minioadmin --secret minioadmin

# No credentials — uses boto3 default chain (env vars, ~/.aws, instance profile, SSO)
brain remote add internal internal-bucket https://s3.amazonaws.com

# List remotes
brain remote list

# Sync
brain sync work

# Remove a remote
brain remote remove work
```

Remotes store name, bucket, prefix, and endpoint in `~/.brain/config.toml`. Credentials are stored in your OS keyring under `brain/remote/<name>` and never written to disk. On a new machine, re-add remotes with `brain remote add` — syncing from scratch is safe (etag tracking re-populates automatically).

## Architecture

```
Ingestion Sources          Pipeline               Query
─────────────────────────────────────────────────────────
Local files       ──┐
S3-compatible     ──┼──→  Parse  →  Chunk  →  Embed  →  Store
remotes (any)     ──┤         ↑                        ↓
Raw import        ──┘    YAML frontmatter          RAG query
```

- **Parser**: Validates YAML frontmatter against a strict schema
- **Chunker**: Splits structured markdown by headers, unstructured text by paragraphs
- **Store**: ChromaDB embedded (fully offline, local file)
- **Embed**: `nomic-embed-text` via Ollama
- **Chat**: `gemma4:e4b` via Ollama
- **Retrieval**: Precision-first vector search with metadata filters, source-safe re-ingestion, diversified context, and cited answers

## Development

```bash
# Run tests
uv run pytest tests/ -v

# Run optional local Ollama smoke eval using the demo notes
brain eval notes-demo/ --run-ollama

# Format code
uv run black brain/ tests/

# Lint and auto-fix
uv run ruff check brain/ tests/ --fix

# Run all quality checks (same as CI)
uv run pre-commit run --all-files

# Install git hooks so checks run on every commit
uv run pre-commit install

# Add a new dependency
uv add <package>

# Add a dev dependency
uv add --dev <package>

# Lock dependencies
uv lock

# Reinstall brain
uv tool install . --reinstall
```

## Backup & Restore

`brain.db` can be backed up and restored at any time. All backups are **encrypted at rest** with a key stored in your OS keyring.

```bash
# Create a backup now
brain backup

# List local backups
brain backup --list

# Restore from a backup file
brain backup --restore ~/.brain/backups/brain-backup-20260427-120000.tar.gz.enc
```

### Automatic daily backups

Enable in `~/.brain/config.toml`:

```toml
[backup]
path = "~/.brain/backups"
retention = 30
daily = true
```

When `daily = true`, Brain checks on each command whether the last backup is older than 24 hours and creates one automatically. The `retention` setting keeps only the most recent *N* backups.

### Recovery passphrase

On first `brain init`, a 12-word recovery passphrase is printed. **Write it down.** If your OS keyring is ever reset, this passphrase is the only way to decrypt your backups. There is no cloud key storage and no backdoor.

> **Security note:** Full-disk encryption (FileVault, BitLocker, LUKS) is recommended to protect the live database on disk. Backup encryption ensures your archives remain safe when copied to external drives or cloud storage.