import os
import tempfile

from typer.testing import CliRunner

from brain.cli import app

runner = CliRunner()


def test_watch_detects_new_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        from pathlib import Path

        import brain.commands.init as init_mod
        import brain.config as config_mod

        orig_default = config_mod.DEFAULT_CONFIG_PATH
        config_mod.DEFAULT_CONFIG_PATH = Path(os.path.join(tmpdir, ".brain", "config.toml"))
        orig_init_dir = init_mod.DEFAULT_CONFIG_DIR
        init_mod.DEFAULT_CONFIG_DIR = Path(os.path.join(tmpdir, ".brain"))

        # mock ollama in add and watch modules
        import brain.commands.add as add_mod
        import brain.commands.watch as watch_mod

        orig_add_client = add_mod.OllamaClient
        orig_watch_client = watch_mod.OllamaClient

        class FakeClient:
            def __init__(self, *a, **k):
                pass

            def embed(self, text, model):
                return [0.1] * 384

        fake = FakeClient
        add_mod.OllamaClient = fake
        watch_mod.OllamaClient = fake

        try:
            runner.invoke(app, ["init"])

            # Create a markdown file in the watched directory
            md_path = os.path.join(tmpdir, "note.md")
            with open(md_path, "w") as f:
                f.write("""---
title: Watch Test
date: 2026-04-26
type: note
---
This is a watched note.
""")

            # Run watch for a very short time by triggering manually
            # Since watch is a long-running process, we'll call the handler directly
            from brain.commands.watch import _process_file

            _process_file(md_path)

            # Check store count increased
            from brain.config import BrainConfig
            from brain.store import BrainStore

            cfg = BrainConfig.load_from()
            store = BrainStore(db_path=cfg.db_path)
            assert store.count() > 0
        finally:
            config_mod.DEFAULT_CONFIG_PATH = orig_default
            init_mod.DEFAULT_CONFIG_DIR = orig_init_dir
            add_mod.OllamaClient = orig_add_client
            watch_mod.OllamaClient = orig_watch_client
