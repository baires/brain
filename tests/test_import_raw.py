import os
import tempfile

from typer.testing import CliRunner

from brain.cli import app

runner = CliRunner()


def test_import_raw_creates_and_stores():
    with tempfile.TemporaryDirectory() as tmpdir:
        from pathlib import Path

        import brain.commands.init as init_mod
        import brain.config as config_mod

        orig_default = config_mod.DEFAULT_CONFIG_PATH
        config_mod.DEFAULT_CONFIG_PATH = Path(os.path.join(tmpdir, ".brain", "config.toml"))
        orig_init_dir = init_mod.DEFAULT_CONFIG_DIR
        init_mod.DEFAULT_CONFIG_DIR = Path(os.path.join(tmpdir, ".brain"))

        import brain.commands.add as add_mod
        import brain.commands.import_raw as import_mod

        orig_add_client = add_mod.OllamaClient

        class FakeClient:
            def __init__(self, *a, **k):
                pass

            def embed(self, text, model):
                return [0.1] * 384

        add_mod.OllamaClient = FakeClient
        import_mod.OllamaClient = FakeClient

        try:
            runner.invoke(app, ["init"])

            raw_path = os.path.join(tmpdir, "raw.txt")
            with open(raw_path, "w") as f:
                f.write("This is raw text content.")

            result = runner.invoke(
                app,
                [
                    "import",
                    raw_path,
                    "--title",
                    "Foo",
                    "--date",
                    "2026-04-26",
                    "--type",
                    "meeting",
                ],
            )
            assert result.exit_code == 0, result.output
            assert "Ingested" in result.output

            # Verify store has chunks
            from brain.config import BrainConfig
            from brain.store import BrainStore

            cfg = BrainConfig.load_from()
            store = BrainStore(db_path=cfg.db_path)
            assert store.count() > 0
        finally:
            config_mod.DEFAULT_CONFIG_PATH = orig_default
            init_mod.DEFAULT_CONFIG_DIR = orig_init_dir
            add_mod.OllamaClient = orig_add_client
            import_mod.OllamaClient = orig_add_client


def test_import_raw_with_structure_uses_model_markdown():
    with tempfile.TemporaryDirectory() as tmpdir:
        from pathlib import Path

        import brain.commands.init as init_mod
        import brain.config as config_mod

        orig_default = config_mod.DEFAULT_CONFIG_PATH
        config_mod.DEFAULT_CONFIG_PATH = Path(os.path.join(tmpdir, ".brain", "config.toml"))
        orig_init_dir = init_mod.DEFAULT_CONFIG_DIR
        init_mod.DEFAULT_CONFIG_DIR = Path(os.path.join(tmpdir, ".brain"))

        import brain.commands.import_raw as import_mod

        orig_client = import_mod.OllamaClient

        class FakeClient:
            def __init__(self, *a, **k):
                pass

            def embed(self, text, model):
                return [0.1] * 384

            def chat(self, prompt, model, system=None):
                assert "Structure the raw transcript" in prompt
                assert "Nimbus raw transcript" in prompt
                structured = """---
title: Nimbus Sync
date: 2026-04-27
type: meeting
tags: [nimbus]
source: transcript
---

## Summary

Nimbus onboarding sync.

## Action Items

- **Priya**: Rewrite checklist copy.
- **Marco**: Update CSV template.
"""
                yield structured

        import_mod.OllamaClient = FakeClient

        try:
            runner.invoke(app, ["init"])
            raw_path = os.path.join(tmpdir, "raw-transcript.txt")
            with open(raw_path, "w") as f:
                f.write("Nimbus raw transcript. Priya owns checklist. Marco owns CSV template.")

            result = runner.invoke(
                app,
                [
                    "import",
                    raw_path,
                    "--title",
                    "Nimbus Sync",
                    "--date",
                    "2026-04-27",
                    "--type",
                    "meeting",
                    "--tag",
                    "nimbus",
                    "--structure",
                ],
            )
            assert result.exit_code == 0, result.output
            assert "Structured" in result.output
            assert "Ingested" in result.output

            from brain.config import BrainConfig
            from brain.store import BrainStore

            cfg = BrainConfig.load_from()
            store = BrainStore(db_path=cfg.db_path)
            results = store.query(embedding=[0.1] * 384, n_results=10)
            assert any("Action Items" in r["metadata"]["breadcrumbs"] for r in results)
            assert any("Rewrite checklist copy" in r["text"] for r in results)
        finally:
            config_mod.DEFAULT_CONFIG_PATH = orig_default
            init_mod.DEFAULT_CONFIG_DIR = orig_init_dir
            import_mod.OllamaClient = orig_client
