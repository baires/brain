from datetime import date

import pytest

from brain.parser import ParseError, parse_document
from brain.schema import DocumentType


def test_parse_valid_frontmatter():
    raw = """---
title: Weekly Sync
date: 2026-04-26
type: meeting
tags: [sync, engineering]
---
Discussed roadmap and action items.
"""
    doc = parse_document(raw, source_path="/tmp/test.md")
    assert doc.meta.title == "Weekly Sync"
    assert doc.meta.date == date(2026, 4, 26)
    assert doc.meta.type == DocumentType.meeting
    assert doc.meta.tags == ["sync", "engineering"]
    assert "roadmap" in doc.content


def test_parse_missing_frontmatter_raises():
    raw = "Just some plain text without frontmatter."
    with pytest.raises(ParseError):
        parse_document(raw, source_path="/tmp/plain.txt")


def test_parse_minimal_frontmatter():
    raw = """---
title: Minimal
date: 2026-04-26
type: note
---
Content here.
"""
    doc = parse_document(raw, source_path="/tmp/min.md")
    assert doc.meta.title == "Minimal"
    assert doc.meta.type == DocumentType.note
    assert doc.content.strip() == "Content here."
