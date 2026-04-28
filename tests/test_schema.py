from datetime import date

import pytest
from pydantic import ValidationError

from brain.schema import BrainDocument, DocumentMeta, DocumentType


def test_valid_document_meta():
    meta = DocumentMeta(title="Meeting Notes", date=date(2026, 4, 26), type=DocumentType.meeting)
    assert meta.title == "Meeting Notes"
    assert meta.date == date(2026, 4, 26)
    assert meta.type == DocumentType.meeting
    assert meta.tags == []


def test_missing_date_fails():
    with pytest.raises(ValidationError) as exc_info:
        DocumentMeta(title="No Date", type=DocumentType.note)
    assert "date" in str(exc_info.value)


def test_invalid_type_fails():
    with pytest.raises(ValidationError) as exc_info:
        DocumentMeta(title="Bad Type", date=date(2026, 4, 26), type="invalid_type")
    assert "type" in str(exc_info.value)


def test_brain_document_roundtrip():
    meta = DocumentMeta(title="Hello", date=date(2026, 4, 26), type=DocumentType.note)
    doc = BrainDocument(meta=meta, content="Body text here.")
    assert doc.content == "Body text here."
    assert doc.meta.title == "Hello"
