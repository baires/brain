# Routines

Routines are configurable, repeatable actions that run against your brain data. They can be triggered on a schedule, by events (like ingesting new notes or creating a backup), or manually from the CLI.

Routines are **optional and lazy** — if you don't configure any, the feature is completely invisible and costs nothing.

---

## Quick example

Add this to `~/.brain/config.toml`:

```toml
[[routines]]
name = "morning-summary"
action = "email"
trigger = { type = "schedule", value = "0 9 * * *" }
query = "meetings yesterday"
params = { to = "you@example.com", subject = "Daily Brain Summary", body = "Your notes are ready." }

[[routines]]
name = "backup-alert"
action = "slack"
trigger = { type = "event", value = "on_backup" }
params = { webhook_url = "https://hooks.slack.com/services/...", message = "Brain backup completed." }
```

Then run the daemon:

```bash
brain routine daemon
```

Or execute a routine manually:

```bash
brain routine run morning-summary
```

---

## CLI commands

```bash
# List configured routines and available actions
brain routine list

# Run a routine immediately
brain routine run <name>

# Start the scheduler daemon
brain routine daemon

# Enable or disable a routine (persists to config.toml)
brain routine enable <name>
brain routine disable <name>
```

---

## Triggers

Every routine needs a `trigger`. There are three kinds:

### Schedule

Runs repeatedly using a cron expression or an interval.

```toml
# Every day at 9:00 AM
trigger = { type = "schedule", value = "0 9 * * *" }

# Every 6 hours
trigger = { type = "schedule", value = "interval:6h" }

# Every 30 minutes
trigger = { type = "schedule", value = "interval:30m" }
```

Supported interval units: `s`, `m`, `h`, `d`.

### Event

Fires when something happens inside Brain.

```toml
trigger = { type = "event", value = "on_ingest" }
trigger = { type = "event", value = "on_backup" }
```

Event-driven routines run **inline** in the CLI process that triggered the event. You don't need the daemon running for them to work.

### Manual

No automatic trigger. Only runs when you explicitly call `brain routine run <name>`.

```toml
trigger = { type = "manual" }
```

---

## Querying brain data

Routines aren't limited to static messages. You can pull live data from your brain store and include it in emails, Slack messages, PDFs, or Google Docs.

### The `query` field

Add a `query` string to any routine. Before the action runs, Brain searches your notes using the same RAG pipeline as `brain ask` and passes the results to the action.

```toml
[[routines]]
name = "morning-recap"
action = "slack"
trigger = { type = "schedule", value = "0 9 * * *" }
query = "meetings yesterday"
params = { webhook_url = "https://hooks.slack.com/services/...", message = "Morning recap:" }
```

When this routine fires, Brain:
1. Embeds `"meetings yesterday"` via Ollama
2. Runs a vector search against your local ChromaDB store
3. Formats the top results (title, date, source path, text snippet)
4. Appends them to the Slack message, email body, PDF content, or Google Doc

You can also set `query` inside `params` for action-specific overrides:

```toml
params = { query = "action items last 7 days", n_results = 10 }
```

### Controlling result count

By default, actions fetch `5` results. Override per action:

```toml
params = { query = "sales meetings", n_results = 10 }
```

### What happens when nothing matches

If the query returns no results, the action includes a "_No matching notes found._" placeholder so you know the routine ran but your brain was empty on that topic.

---

## Built-in actions

These ship with Brain and are ready to use.

> **Note:** Actions that support `query` (`email`, `slack`, `pdf_export`, `google_doc`) will automatically append search results to their output when `query` is set.

### `echo`

Returns a message. Useful for testing.

```toml
[[routines]]
name = "ping"
action = "echo"
trigger = { type = "manual" }
params = { message = "pong" }
```

### `shell`

Runs a shell command. The routine name and trigger info are injected as environment variables.

```toml
[[routines]]
name = "deploy-notes"
action = "shell"
trigger = { type = "manual" }
params = { command = "rsync -av ~/.brain/notes/ server:/var/notes/", timeout = 120 }
```

Available env vars:
- `BRAIN_ROUTINE_NAME`
- `BRAIN_TRIGGER_TYPE`
- `BRAIN_TRIGGER_VALUE`

You can add custom env vars via `params.env`:

```toml
params = { command = "./notify.sh", env = { TARGET = "team" } }
```

### `email`

Sends email via SMTP. Supports `query` to include search results in the body.

```toml
[[routines]]
name = "morning-email"
action = "email"
trigger = { type = "schedule", value = "0 9 * * *" }
query = "meetings yesterday"
params = {
  to = "you@example.com",
  subject = "Brain digest",
  body = "Here is what happened yesterday:",
  smtp_host = "smtp.gmail.com",
  smtp_port = 587,
  smtp_tls = true,
  smtp_user = "you@gmail.com",
  smtp_password = "app-password"
}
```

Parameters:
- `to` (required)
- `subject`
- `body`
- `from` — sender address (defaults to `smtp_user`)
- `smtp_host` — default `localhost`
- `smtp_port` — default `25`
- `smtp_tls` — default `false`
- `smtp_user`
- `smtp_password`
- `query` — override the routine-level query
- `n_results` — number of search results to include (default `5`)

### `slack`

Posts a message to a Slack incoming webhook. Supports `query` to include search results.

```toml
[[routines]]
name = "morning-recap"
action = "slack"
trigger = { type = "schedule", value = "0 9 * * *" }
query = "meetings yesterday"
params = { webhook_url = "https://hooks.slack.com/services/...", message = "Morning recap:" }
```

Parameters:
- `webhook_url` (required)
- `message`
- `query` — override the routine-level query
- `n_results` — number of search results to include (default `5`)

### `pdf_export`

Generates a PDF file. Uses `fpdf2` under the hood. Supports `query` to populate the PDF with search results.

```toml
[[routines]]
name = "weekly-pdf"
action = "pdf_export"
trigger = { type = "schedule", value = "0 9 * * 1" }
query = "important notes last 7 days"
params = { output_path = "~/weekly-notes.pdf", title = "Weekly Notes", body = "This week's highlights:" }
```

Parameters:
- `output_path` (required)
- `title`
- `body`
- `query` — override the routine-level query
- `n_results` — number of search results to include (default `20`)

### `google_doc`

Appends text to a Google Doc. Requires Google API client libraries. Supports `query` to include search results.

```toml
[[routines]]
name = "weekly-report"
action = "google_doc"
trigger = { type = "schedule", value = "0 17 * * 5" }
query = "decisions this week"
params = { doc_id = "1a2b3c...", content = "Week summary:", credentials_path = "/path/to/service-account.json" }
```

Parameters:
- `doc_id` (required) — the Google Doc ID from the URL
- `content` — text to append
- `credentials_path` — path to a Google service-account JSON key
- `query` — override the routine-level query
- `n_results` — number of search results to include (default `10`)

If the Google libraries aren't installed, the routine returns a helpful error message telling you how to install them:

```bash
uv pip install google-auth google-auth-oauthlib google-api-python-client
```

---

## Routine state & retries

Routine execution state is stored in `~/.brain/state.db` (SQLite). It tracks:

- `last_run` — when the routine last executed
- `next_run` — when it should run next
- `failures` — consecutive failure count
- `last_error` — the last error message

### Retry behavior

If a routine fails, Brain applies **exponential backoff**:

```
delay = 2^failures × 60 seconds  (capped at 1 hour)
```

After the configured number of `retries` (default `3`), the routine stops auto-retrying and requires manual intervention:

```bash
brain routine run <name>
```

You can customize retries per routine:

```toml
[[routines]]
name = "critical-alert"
action = "slack"
retries = 5
```

---

## Creating your own action

Actions are Python classes that inherit from `RoutineAction` and implement `run()`.

### 1. Write the action

Create a file anywhere in your Python path (for example, inside a local package or a separate repo):

```python
# my_routines/telegram.py
from brain.routines.models import (
    RoutineAction,
    RoutineContext,
    RoutineResult,
    format_query_results,
)
from brain.routines.registry import register_builtin


@register_builtin
class TelegramAction(RoutineAction):
    name = "telegram"

    def run(self, context: RoutineContext, params: dict) -> RoutineResult:
        token = params.get("bot_token")
        chat_id = params.get("chat_id")
        message = params.get("message", f"Routine {context.routine_name} triggered.")

        if not token or not chat_id:
            return RoutineResult(success=False, message="Missing bot_token or chat_id")

        # Optional: pull live data from brain
        query = params.get("query") or context.query
        if query:
            results = context.search(query, n_results=params.get("n_results", 5))
            recap = format_query_results(results, plain=True)
            message = f"{message}\n\n{recap}"

        import requests
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        response = requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=30)
        response.raise_for_status()

        return RoutineResult(success=True, message="Message sent")
```

`RoutineContext` gives you access to:
- `context.config` — the loaded `BrainConfig` (ollama URL, DB path, etc.)
- `context.routine_name` — the name of the running routine
- `context.trigger` — the trigger that fired (`type`, `value`)
- `context.query` — the query string configured on the routine (if any)
- `context.search(query, n_results=5)` — run a live vector search against your brain store and get back a list of result dicts with `text` and `metadata`

`RoutineResult` expects:
- `success` — boolean
- `message` — a human-readable string
- `data` — optional dict for extra structured output

### 2. Register via entry point

If you package your action as a proper Python package, add it to `pyproject.toml`:

```toml
[project.entry-points."brain.routines"]
my_telegram = "my_routines.telegram:TelegramAction"
```

After installing the package, Brain will discover `telegram` automatically alongside the built-ins.

### 3. Use it

```toml
[[routines]]
name = "alert-me"
action = "telegram"
trigger = { type = "event", value = "on_backup" }
params = { bot_token = "...", chat_id = "...", message = "Backup complete!" }
```

---

## Tips

- Start with `trigger = { type = "manual" }` while developing a new routine, then switch to a schedule or event once it works.
- Use `brain routine list` to verify your routine is parsed correctly and its action is recognized.
- Event-driven routines are great for lightweight reactions (Slack ping after backup). Scheduled routines are better for periodic reports (daily email digest).
- The daemon is single-node and in-process. If you need distributed scheduling, run the daemon on one machine and treat Brain as a local dependency.
