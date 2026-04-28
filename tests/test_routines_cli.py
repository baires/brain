import tempfile
from pathlib import Path

from typer.testing import CliRunner

from brain.cli import app

runner = CliRunner()


def test_routine_list_empty():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.toml"
        # Write a minimal config without routines
        with open(config_path, "w") as f:
            f.write('ollama_url = "http://localhost:11434"\n')

        import brain.config as config_mod

        orig_default = config_mod.DEFAULT_CONFIG_PATH
        config_mod.DEFAULT_CONFIG_PATH = config_path
        try:
            result = runner.invoke(app, ["routine", "list"])
            assert result.exit_code == 0, result.output
            assert "No routines configured" in result.output
            assert "echo" in result.output
        finally:
            config_mod.DEFAULT_CONFIG_PATH = orig_default


def test_routine_run():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.toml"
        config_path.write_text("""
ollama_url = "http://localhost:11434"

[[routines]]
name = "test-echo"
action = "echo"
trigger = { type = "manual" }
params = { message = "hello from cli" }
""")

        import brain.config as config_mod

        orig_default = config_mod.DEFAULT_CONFIG_PATH
        config_mod.DEFAULT_CONFIG_PATH = config_path
        try:
            result = runner.invoke(app, ["routine", "run", "test-echo"])
            assert result.exit_code == 0, result.output
            assert "succeeded" in result.output
            assert "hello from cli" in result.output
        finally:
            config_mod.DEFAULT_CONFIG_PATH = orig_default


def test_routine_list_with_routines():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.toml"
        config_path.write_text("""
ollama_url = "http://localhost:11434"

[[routines]]
name = "morning-summary"
action = "echo"
trigger = { type = "schedule", value = "0 9 * * *" }
params = { message = "Good morning" }

[[routines]]
name = "backup-notify"
action = "nonexistent"
trigger = { type = "event", value = "on_backup" }
""")

        import brain.config as config_mod

        orig_default = config_mod.DEFAULT_CONFIG_PATH
        config_mod.DEFAULT_CONFIG_PATH = config_path
        try:
            result = runner.invoke(app, ["routine", "list"])
            assert result.exit_code == 0, result.output
            assert "morning-summary" in result.output
            assert "echo" in result.output
            assert "0 9 * * *" in result.output
            assert "backup-notify" in result.output
            assert "nonexistent" in result.output
            assert "on_backup" in result.output
            assert "enabled" in result.output
            assert "action missing" in result.output  # nonexistent is not a built-in
        finally:
            config_mod.DEFAULT_CONFIG_PATH = orig_default
