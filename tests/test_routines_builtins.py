import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from brain.routines.builtins.echo import EchoAction
from brain.routines.builtins.email import EmailAction
from brain.routines.builtins.pdf_export import PdfExportAction
from brain.routines.builtins.shell import ShellAction
from brain.routines.builtins.slack import SlackAction
from brain.routines.models import RoutineContext, TriggerSpec


def make_context(name: str = "test", trigger_type: str = "manual") -> RoutineContext:
    from brain.config import BrainConfig

    return RoutineContext(
        config=BrainConfig(),
        routine_name=name,
        trigger=TriggerSpec(type=trigger_type),
    )


def test_echo_action():
    action = EchoAction()
    ctx = make_context()
    result = action.run(ctx, {"message": "hello"})
    assert result.success is True
    assert result.message == "hello"


def test_shell_action_success():
    action = ShellAction()
    ctx = make_context()
    result = action.run(ctx, {"command": "echo hello_from_test"})
    assert result.success is True
    assert "hello_from_test" in result.message


def test_shell_action_failure():
    action = ShellAction()
    ctx = make_context()
    result = action.run(ctx, {"command": "exit 1"})
    assert result.success is False


def test_shell_action_missing_command():
    action = ShellAction()
    ctx = make_context()
    result = action.run(ctx, {})
    assert result.success is False
    assert "Missing" in result.message


def test_slack_action_success():
    action = SlackAction()
    ctx = make_context()
    with patch("brain.routines.builtins.slack.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=lambda: None)
        result = action.run(ctx, {"webhook_url": "https://hooks.slack.com/test", "message": "hi"})
        assert result.success is True
        mock_post.assert_called_once()


def test_slack_action_missing_webhook():
    action = SlackAction()
    ctx = make_context()
    result = action.run(ctx, {})
    assert result.success is False
    assert "webhook_url" in result.message


def test_email_action_success():
    action = EmailAction()
    ctx = make_context()
    with patch("brain.routines.builtins.email.smtplib.SMTP") as mock_smtp:
        instance = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=instance)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)
        result = action.run(ctx, {"to": "test@example.com", "subject": "Test", "body": "Hello"})
        assert result.success is True
        instance.send_message.assert_called_once()


def test_email_action_missing_to():
    action = EmailAction()
    ctx = make_context()
    result = action.run(ctx, {})
    assert result.success is False
    assert "to" in result.message


def test_pdf_export_action():
    action = PdfExportAction()
    ctx = make_context()
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.pdf"
        result = action.run(
            ctx, {"output_path": str(path), "title": "Test PDF", "body": "Hello world"}
        )
        assert result.success is True
        assert path.exists()
        assert path.stat().st_size > 0


def test_pdf_export_missing_path():
    action = PdfExportAction()
    ctx = make_context()
    result = action.run(ctx, {})
    assert result.success is False
    assert "output_path" in result.message
