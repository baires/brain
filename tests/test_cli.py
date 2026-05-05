import os
import tempfile
from datetime import date

from typer.testing import CliRunner

from brain.cli import app

runner = CliRunner()


def test_init_creates_config_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = os.path.join(tmpdir, ".brain")
        import brain.commands.init as init_mod

        orig_path = init_mod.DEFAULT_CONFIG_DIR
        orig_get_key = init_mod.get_or_create_backup_key
        init_mod.DEFAULT_CONFIG_DIR = config_dir
        init_mod.get_or_create_backup_key = lambda: (
            b"key",
            "word one two three four five six seven eight nine ten eleven twelve",
        )
        try:
            result = runner.invoke(app, ["init"])
            assert result.exit_code == 0, result.output
            assert os.path.isdir(config_dir)
            assert os.path.isfile(os.path.join(config_dir, "config.toml"))
            assert "BACKUP RECOVERY PASSPHRASE" in result.output
            assert "word one two three four five" in result.output
            assert "six seven eight nine ten eleven twelve" in result.output
        finally:
            init_mod.DEFAULT_CONFIG_DIR = orig_path
            init_mod.get_or_create_backup_key = orig_get_key


def test_init_idempotent_skips_passphrase():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = os.path.join(tmpdir, ".brain")
        import brain.commands.init as init_mod

        orig_path = init_mod.DEFAULT_CONFIG_DIR
        orig_get_key = init_mod.get_or_create_backup_key
        init_mod.DEFAULT_CONFIG_DIR = config_dir
        init_mod.get_or_create_backup_key = lambda: (b"key", None)
        try:
            result = runner.invoke(app, ["init"])
            assert result.exit_code == 0, result.output
            assert "Recovery Passphrase" not in result.output
        finally:
            init_mod.DEFAULT_CONFIG_DIR = orig_path
            init_mod.get_or_create_backup_key = orig_get_key


def test_add_ingests_markdown():
    with tempfile.TemporaryDirectory() as tmpdir:
        md_path = os.path.join(tmpdir, "note.md")
        with open(md_path, "w") as f:
            f.write("""---
title: Test Note
date: 2026-04-26
type: note
---
This is a test note.
""")
        from pathlib import Path

        import brain.commands.init as init_mod
        import brain.config as config_mod

        orig_config_path = config_mod.DEFAULT_CONFIG_PATH
        orig_config_dir = init_mod.DEFAULT_CONFIG_DIR
        brain_dir = os.path.join(tmpdir, ".brain")
        config_mod.DEFAULT_CONFIG_PATH = Path(os.path.join(brain_dir, "config.toml"))
        init_mod.DEFAULT_CONFIG_DIR = Path(brain_dir)
        try:
            result = runner.invoke(app, ["init"])
            assert result.exit_code == 0

            import brain.commands.add as add_mod

            orig_provider = add_mod.get_provider

            class _FakeProvider:
                def embed(self, text, model):
                    return [0.1] * 384

                def chat(self, prompt, model, system=None):
                    yield ""

            add_mod.get_provider = lambda cfg: _FakeProvider()
            try:
                result = runner.invoke(app, ["add", md_path])
                assert result.exit_code == 0, result.output
                assert "Ingested" in result.output or "1 file" in result.output
            finally:
                add_mod.get_provider = orig_provider
        finally:
            config_mod.DEFAULT_CONFIG_PATH = orig_config_path
            init_mod.DEFAULT_CONFIG_DIR = orig_config_dir


def test_status_prints_info():
    with tempfile.TemporaryDirectory() as tmpdir:
        from pathlib import Path

        import brain.config as config_mod

        orig_default = config_mod.DEFAULT_CONFIG_PATH
        config_mod.DEFAULT_CONFIG_PATH = Path(os.path.join(tmpdir, ".brain", "config.toml"))
        import brain.commands.init as init_mod

        orig_init_dir = init_mod.DEFAULT_CONFIG_DIR
        init_mod.DEFAULT_CONFIG_DIR = Path(os.path.join(tmpdir, ".brain"))
        try:
            runner.invoke(app, ["init"])
            result = runner.invoke(app, ["status"])
            assert result.exit_code == 0, result.output
            assert "Documents:" in result.output
            assert "DB path:" in result.output
            assert "gemma4:e4b" in result.output
        finally:
            config_mod.DEFAULT_CONFIG_PATH = orig_default
            init_mod.DEFAULT_CONFIG_DIR = orig_init_dir


def test_ask_renders_markdown_response():
    with tempfile.TemporaryDirectory() as tmpdir:
        from pathlib import Path

        import brain.commands.ask as ask_mod
        import brain.commands.init as init_mod
        import brain.config as config_mod

        brain_dir = os.path.join(tmpdir, ".brain")
        orig_default = config_mod.DEFAULT_CONFIG_PATH
        orig_init_dir = init_mod.DEFAULT_CONFIG_DIR
        orig_engine = ask_mod.QueryEngine
        config_mod.DEFAULT_CONFIG_PATH = Path(os.path.join(brain_dir, "config.toml"))
        init_mod.DEFAULT_CONFIG_DIR = Path(brain_dir)

        class FakeEngine:
            def __init__(self, *a, **k):
                pass

            def ask(self, question, filters=None):
                yield "## Answer\nHere is **some markdown**."

        ask_mod.QueryEngine = FakeEngine

        try:
            runner.invoke(app, ["init"])
            result = runner.invoke(app, ["ask", "what is X?"])
            assert result.exit_code == 0, result.output
            assert "Answer" in result.output
            assert "some markdown" in result.output
        finally:
            config_mod.DEFAULT_CONFIG_PATH = orig_default
            init_mod.DEFAULT_CONFIG_DIR = orig_init_dir
            ask_mod.QueryEngine = orig_engine


def test_backup_create_and_list():
    with tempfile.TemporaryDirectory() as tmpdir:
        from pathlib import Path

        import brain.backup as backup_mod
        import brain.commands.init as init_mod
        import brain.config as config_mod

        brain_dir = os.path.join(tmpdir, ".brain")
        orig_default = config_mod.DEFAULT_CONFIG_PATH
        orig_init_dir = init_mod.DEFAULT_CONFIG_DIR
        config_mod.DEFAULT_CONFIG_PATH = Path(os.path.join(brain_dir, "config.toml"))
        init_mod.DEFAULT_CONFIG_DIR = Path(brain_dir)

        try:
            runner.invoke(app, ["init"])
            db_path = Path(brain_dir) / "brain.db"
            db_path.mkdir()
            (db_path / "chroma.sqlite3").write_text("fake")
            config_toml = Path(brain_dir) / "config.toml"
            with open(config_toml, "a") as f:
                f.write(f'backup_path = "{brain_dir}/backups"\n')
            orig_get_key = backup_mod.get_or_create_backup_key
            backup_mod.get_or_create_backup_key = lambda: (
                b"JF3bfm6rkRTH8lTWEkQJEG6djZHOGsil2uhdbkcmglo=",
                None,
            )
            try:
                result = runner.invoke(app, ["backup"])
                assert result.exit_code == 0, result.output
                assert "Backup created:" in result.output
                assert brain_dir in result.output

                result = runner.invoke(app, ["backup", "--list"])
                assert result.exit_code == 0, result.output
                assert "brain-backup-" in result.output
            finally:
                backup_mod.get_or_create_backup_key = orig_get_key
        finally:
            config_mod.DEFAULT_CONFIG_PATH = orig_default
            init_mod.DEFAULT_CONFIG_DIR = orig_init_dir


def test_backup_restore():
    with tempfile.TemporaryDirectory() as tmpdir:
        from pathlib import Path

        import brain.backup as backup_mod
        import brain.commands.init as init_mod
        import brain.config as config_mod

        brain_dir = os.path.join(tmpdir, ".brain")
        orig_default = config_mod.DEFAULT_CONFIG_PATH
        orig_init_dir = init_mod.DEFAULT_CONFIG_DIR
        config_mod.DEFAULT_CONFIG_PATH = Path(os.path.join(brain_dir, "config.toml"))
        init_mod.DEFAULT_CONFIG_DIR = Path(brain_dir)

        try:
            runner.invoke(app, ["init"])
            db_path = Path(brain_dir) / "brain.db"
            db_path.mkdir()
            (db_path / "chroma.sqlite3").write_text("fake")
            config_toml = Path(brain_dir) / "config.toml"
            with open(config_toml, "a") as f:
                f.write(f'backup_path = "{brain_dir}/backups"\n')
            orig_get_key = backup_mod.get_or_create_backup_key
            backup_mod.get_or_create_backup_key = lambda: (
                b"JF3bfm6rkRTH8lTWEkQJEG6djZHOGsil2uhdbkcmglo=",
                None,
            )
            try:
                result = runner.invoke(app, ["backup"])
                assert result.exit_code == 0, result.output
                backup_file = result.output.split("Backup created: ")[1].strip()
                assert brain_dir in backup_file

                (db_path / "extra.txt").write_text("extra")

                result = runner.invoke(app, ["backup", "--restore", backup_file])
                assert result.exit_code == 0, result.output
                assert "Restored from" in result.output
                assert not (db_path / "extra.txt").exists()
            finally:
                backup_mod.get_or_create_backup_key = orig_get_key
        finally:
            config_mod.DEFAULT_CONFIG_PATH = orig_default
            init_mod.DEFAULT_CONFIG_DIR = orig_init_dir


def test_ask_last_filter_and_show_context():
    with tempfile.TemporaryDirectory() as tmpdir:
        from pathlib import Path

        import brain.commands.add as add_mod
        import brain.commands.ask as ask_mod
        import brain.commands.init as init_mod
        import brain.config as config_mod

        orig_default = config_mod.DEFAULT_CONFIG_PATH
        orig_init_dir = init_mod.DEFAULT_CONFIG_DIR
        orig_add_provider = add_mod.get_provider
        orig_ask_provider = ask_mod.get_provider
        orig_today = ask_mod._today
        brain_dir = os.path.join(tmpdir, ".brain")
        config_mod.DEFAULT_CONFIG_PATH = Path(os.path.join(brain_dir, "config.toml"))
        init_mod.DEFAULT_CONFIG_DIR = Path(brain_dir)

        class _FakeProvider:
            def embed(self, text, model):
                if "meeting" in text.lower():
                    return [0.9] * 384
                return [0.1] * 384

            def chat(self, prompt, model, system=None):
                yield "Use the recent meeting [1]."

        add_mod.get_provider = lambda cfg: _FakeProvider()
        ask_mod.get_provider = lambda cfg: _FakeProvider()
        ask_mod._today = lambda: date(2026, 4, 27)

        import brain.cli as cli_mod

        orig_maybe_backup = cli_mod._maybe_auto_backup
        cli_mod._maybe_auto_backup = lambda: None

        try:
            runner.invoke(app, ["init"])
            old_path = os.path.join(tmpdir, "old.md")
            recent_path = os.path.join(tmpdir, "recent.md")
            with open(old_path, "w") as f:
                f.write("""---
title: Old Meeting
date: 2026-01-01
type: meeting
---
Old meeting note.
""")
            with open(recent_path, "w") as f:
                f.write("""---
title: Recent Meeting
date: 2026-04-26
type: meeting
---
Recent meeting note.
""")
            assert runner.invoke(app, ["add", tmpdir]).exit_code == 0
            result = runner.invoke(
                app, ["ask", "meeting?", "--type", "meeting", "--last", "7", "--show-context"]
            )
            assert result.exit_code == 0, result.output
            assert "Retrieved context:" in result.output
            assert "Recent Meeting" in result.output
            assert "Old Meeting" not in result.output
            assert "distance=" in result.output
            assert "Use the recent meeting [1]." in result.output
        finally:
            config_mod.DEFAULT_CONFIG_PATH = orig_default
            init_mod.DEFAULT_CONFIG_DIR = orig_init_dir
            add_mod.get_provider = orig_add_provider
            ask_mod.get_provider = orig_ask_provider
            ask_mod._today = orig_today
            cli_mod._maybe_auto_backup = orig_maybe_backup
