from brain.commands.do import _format_for_slack


def test_format_for_slack_bold():
    text = "**Context:** something happened"
    assert _format_for_slack(text) == "*Context:* something happened"


def test_format_for_slack_bullets():
    text = "* bullet one\n* bullet two"
    assert _format_for_slack(text) == "• bullet one\n• bullet two"


def test_format_for_slack_citations():
    text = "deal size [5: notes/demo.md#1] and next steps [2: notes/other.md]"
    assert (
        _format_for_slack(text) == "deal size [5: notes/demo.md] and next steps [2: notes/other.md]"
    )


def test_format_for_slack_preserves_slack_bold():
    text = "*already slack bold*\n* bullet"
    result = _format_for_slack(text)
    assert "*already slack bold*" in result
    assert "• bullet" in result
