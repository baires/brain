from typer.testing import CliRunner

from brain.cli import app

runner = CliRunner()


def test_eval_requires_opt_in_flag():
    result = runner.invoke(app, ["eval", "notes-demo"])
    assert result.exit_code != 0
    assert "--run-ollama" in result.output
