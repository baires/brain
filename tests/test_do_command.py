from unittest.mock import MagicMock, patch

import pytest
import typer

from brain.commands.do import _find_defaults, _parse_instruction, run_do


def test_parse_instruction_slack():
    assert _parse_instruction("send yesterday meetings to slack") == ("slack", "yesterday meetings")
    assert _parse_instruction("post sales update to slack") == ("slack", "sales update")
    assert _parse_instruction("slack my daily recap") == ("slack", "my daily recap")


def test_parse_instruction_email():
    assert _parse_instruction("email me action items") == ("email", "action items")
    assert _parse_instruction("email last week summary") == ("email", "last week summary")


def test_parse_instruction_pdf():
    assert _parse_instruction("create a pdf of sales notes") == ("pdf_export", "sales notes")
    assert _parse_instruction("save meeting notes as pdf") == ("pdf_export", "meeting notes")


def test_parse_instruction_google_doc():
    assert _parse_instruction("post weekly report to google doc") == ("google_doc", "weekly report")


def test_parse_instruction_unknown():
    assert _parse_instruction("what is the weather") is None


def test_find_defaults():
    from brain.config import BrainConfig
    from brain.routines.models import RoutineConfig, TriggerSpec

    cfg = BrainConfig()
    cfg.routines = [
        RoutineConfig(
            name="my-slack",
            action="slack",
            trigger=TriggerSpec(type="manual"),
            params={"webhook_url": "https://example.com"},
        ),
        RoutineConfig(
            name="other",
            action="echo",
            trigger=TriggerSpec(type="manual"),
            params={"message": "hi"},
        ),
    ]
    assert _find_defaults("slack", cfg) == {"webhook_url": "https://example.com"}
    assert _find_defaults("echo", cfg) == {"message": "hi"}
    assert _find_defaults("missing", cfg) == {}


def test_run_do_no_defaults():
    with patch("brain.commands.do.BrainConfig.load_from") as mock_cfg:
        mock_cfg.return_value = MagicMock(routines=[])
        with patch("brain.commands.do._ask_brain", return_value="some answer"):
            # Capture print output
            import io
            import sys

            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                run_do("send test to slack")
                output = sys.stdout.getvalue()
            finally:
                sys.stdout = old_stdout
            assert "No default params found" in output


def test_run_do_slack_success():
    from brain.routines.models import RoutineConfig, TriggerSpec

    with patch("brain.commands.do.BrainConfig.load_from") as mock_cfg:
        cfg = MagicMock()
        cfg.routines = [
            RoutineConfig(
                name="default-slack",
                action="slack",
                trigger=TriggerSpec(type="manual"),
                params={"webhook_url": "https://hooks.slack.com/test"},
            )
        ]
        mock_cfg.return_value = cfg

        with (
            patch("brain.commands.do._ask_brain", return_value="Answer: meetings were productive."),
            patch("brain.commands.do.get_action") as mock_get_action,
        ):
            mock_action_cls = MagicMock()
            mock_instance = MagicMock()
            mock_instance.run.return_value = MagicMock(success=True, message="sent")
            mock_action_cls.return_value = mock_instance
            mock_get_action.return_value = mock_action_cls

            import io
            import sys

            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                run_do("send test to slack")
                output = sys.stdout.getvalue()
            finally:
                sys.stdout = old_stdout

            assert "Delivered via slack" in output
            call_args = mock_instance.run.call_args
            context, params = call_args[0]
            assert "meetings were productive" in params["message"]


def test_run_do_delivery_failure_exits_nonzero():
    from brain.routines.models import RoutineConfig, TriggerSpec

    with patch("brain.commands.do.BrainConfig.load_from") as mock_cfg:
        cfg = MagicMock()
        cfg.routines = [
            RoutineConfig(
                name="default-slack",
                action="slack",
                trigger=TriggerSpec(type="manual"),
                params={"webhook_url": "https://hooks.slack.com/test"},
            )
        ]
        mock_cfg.return_value = cfg

        with (
            patch("brain.commands.do._ask_brain", return_value="Answer."),
            patch("brain.commands.do.get_action") as mock_get_action,
        ):
            mock_action_cls = MagicMock()
            mock_instance = MagicMock()
            mock_instance.run.return_value = MagicMock(success=False, message="webhook failed")
            mock_action_cls.return_value = mock_instance
            mock_get_action.return_value = mock_action_cls

            with pytest.raises(typer.Exit) as exc:
                run_do("send test to slack")

            assert exc.value.exit_code == 1
