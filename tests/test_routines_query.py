from unittest.mock import MagicMock

from brain.routines.builtins.email import EmailAction
from brain.routines.builtins.pdf_export import PdfExportAction
from brain.routines.builtins.slack import SlackAction
from brain.routines.models import RoutineContext, format_query_results


def make_context_with_search(results=None, query=None) -> RoutineContext:
    from brain.config import BrainConfig

    ctx = RoutineContext(
        config=BrainConfig(),
        routine_name="test",
        trigger=MagicMock(),
        query=query,
    )
    ctx.search = MagicMock(return_value=results or [])
    return ctx


def make_context_with_failing_search(query="meetings yesterday") -> RoutineContext:
    from brain.config import BrainConfig

    ctx = RoutineContext(
        config=BrainConfig(),
        routine_name="test",
        trigger=MagicMock(),
        query=query,
    )
    ctx.search = MagicMock(side_effect=RuntimeError("ollama unavailable"))
    return ctx


def test_format_query_results_empty():
    assert "No matching notes" in format_query_results([])


def test_format_query_results_with_data():
    results = [
        {
            "text": "Discussed Q3 roadmap.",
            "metadata": {
                "title": "Product Meeting",
                "source_path": "notes/product.md",
                "date": "2026-04-26",
                "doc_type": "meeting",
            },
        }
    ]
    output = format_query_results(results)
    assert "Product Meeting" in output
    assert "notes/product.md" in output
    assert "Discussed Q3 roadmap" in output


def test_slack_action_with_query():
    action = SlackAction()
    ctx = make_context_with_search(
        query="meetings yesterday",
        results=[
            {
                "text": "Sales sync notes.",
                "metadata": {"title": "Sales Sync", "source_path": "notes/sales.md"},
            }
        ],
    )
    with MagicMock() as mock_post:
        import brain.routines.builtins.slack as slack_mod

        orig_post = slack_mod.requests.post
        slack_mod.requests.post = mock_post
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=lambda: None)
        try:
            result = action.run(
                ctx, {"webhook_url": "https://hooks.slack.com/test", "message": "Morning recap:"}
            )
            assert result.success is True
            call_args = mock_post.call_args
            payload = call_args[1]["data"] if "data" in call_args[1] else call_args[0][1]
            assert "Morning recap:" in payload
            assert "Sales Sync" in payload
        finally:
            slack_mod.requests.post = orig_post


def test_slack_action_reports_query_failure_without_sending():
    action = SlackAction()
    ctx = make_context_with_failing_search()

    import brain.routines.builtins.slack as slack_mod

    orig_post = slack_mod.requests.post
    slack_mod.requests.post = MagicMock()
    try:
        result = action.run(
            ctx, {"webhook_url": "https://hooks.slack.com/test", "message": "Morning recap:"}
        )
        assert result.success is False
        assert "Query failed" in result.message
        slack_mod.requests.post.assert_not_called()
    finally:
        slack_mod.requests.post = orig_post


def test_email_action_with_query():
    action = EmailAction()
    ctx = make_context_with_search(
        query="meetings yesterday",
        results=[
            {
                "text": "Engineering standup notes.",
                "metadata": {"title": "Standup", "source_path": "notes/standup.md"},
            }
        ],
    )
    with MagicMock() as mock_smtp:
        import brain.routines.builtins.email as email_mod

        orig_smtp = email_mod.smtplib.SMTP
        email_mod.smtplib.SMTP = mock_smtp
        instance = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=instance)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)
        try:
            result = action.run(
                ctx, {"to": "test@example.com", "subject": "Recap", "body": "Here is your recap:"}
            )
            assert result.success is True
            call_args = instance.send_message.call_args
            msg = call_args[0][0]
            body = msg.get_payload()[0].get_payload()
            assert "Here is your recap:" in body
            assert "Standup" in body
        finally:
            email_mod.smtplib.SMTP = orig_smtp


def test_pdf_export_action_with_query():
    import tempfile
    from pathlib import Path

    action = PdfExportAction()
    ctx = make_context_with_search(
        query="meetings yesterday",
        results=[
            {
                "text": "Board meeting notes.",
                "metadata": {"title": "Board Meeting", "source_path": "notes/board.md"},
            }
        ],
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.pdf"
        result = action.run(ctx, {"output_path": str(path), "query": "meetings yesterday"})
        assert result.success is True
        assert path.exists()
        assert path.stat().st_size > 0
