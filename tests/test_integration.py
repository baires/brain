import os
import tempfile

from typer.testing import CliRunner

from brain.cli import app

runner = CliRunner()


def test_integration_add_then_ask():
    with tempfile.TemporaryDirectory() as tmpdir:
        from pathlib import Path

        import brain.commands.init as init_mod
        import brain.config as config_mod

        orig_default = config_mod.DEFAULT_CONFIG_PATH
        config_mod.DEFAULT_CONFIG_PATH = Path(os.path.join(tmpdir, ".brain", "config.toml"))
        orig_init_dir = init_mod.DEFAULT_CONFIG_DIR
        init_mod.DEFAULT_CONFIG_DIR = Path(os.path.join(tmpdir, ".brain"))

        import brain.commands.add as add_mod
        import brain.commands.ask as ask_mod

        orig_add_client = add_mod.OllamaClient
        orig_ask_client = ask_mod.OllamaClient

        class FakeEmbedClient:
            def __init__(self, *a, **k):
                pass

            def embed(self, text, model):
                return [0.1] * 384

        class FakeChatClient:
            def __init__(self, *a, **k):
                pass

            def embed(self, text, model):
                return [0.1] * 384

            def chat(self, prompt, model, system=None):
                # Yield tokens that reference the action item from context
                yield from [
                    "The",
                    " action",
                    " item",
                    " is",
                    ":",
                    " fix",
                    " the",
                    " login",
                    " bug",
                    ".",
                ]

        add_mod.OllamaClient = FakeEmbedClient
        ask_mod.OllamaClient = FakeChatClient

        try:
            runner.invoke(app, ["init"])

            md_path = os.path.join(tmpdir, "meeting.md")
            with open(md_path, "w") as f:
                f.write(
                    """---
title: Sprint Planning
date: 2026-04-26
type: meeting
---
## Action Items

- fix the login bug
- update API docs
"""
                )

            result = runner.invoke(app, ["add", md_path])
            assert result.exit_code == 0, result.output

            result = runner.invoke(app, ["ask", "what are the action items?"])
            assert result.exit_code == 0, result.output
            assert "fix the login bug" in result.output
        finally:
            config_mod.DEFAULT_CONFIG_PATH = orig_default
            init_mod.DEFAULT_CONFIG_DIR = orig_init_dir
            add_mod.OllamaClient = orig_add_client
            ask_mod.OllamaClient = orig_ask_client
