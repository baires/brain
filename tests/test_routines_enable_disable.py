import tempfile
from pathlib import Path

from typer.testing import CliRunner

from brain.cli import app

runner = CliRunner()


def test_routine_enable_disable():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.toml"
        config_path.write_text("""
ollama_url = "http://localhost:11434"

[[routines]]
name = "test-echo"
action = "echo"
trigger = { type = "manual" }
enabled = false
""")

        import brain.config as config_mod

        orig_default = config_mod.DEFAULT_CONFIG_PATH
        config_mod.DEFAULT_CONFIG_PATH = config_path
        try:
            result = runner.invoke(app, ["routine", "list"])
            assert result.exit_code == 0, result.output
            assert "disabled" in result.output

            result = runner.invoke(app, ["routine", "enable", "test-echo"])
            assert result.exit_code == 0, result.output
            assert "enabled" in result.output

            result = runner.invoke(app, ["routine", "list"])
            assert result.exit_code == 0, result.output
            assert "enabled" in result.output
            assert "disabled" not in result.output

            result = runner.invoke(app, ["routine", "disable", "test-echo"])
            assert result.exit_code == 0, result.output
            assert "disabled" in result.output

            result = runner.invoke(app, ["routine", "list"])
            assert result.exit_code == 0, result.output
            assert "disabled" in result.output
        finally:
            config_mod.DEFAULT_CONFIG_PATH = orig_default
