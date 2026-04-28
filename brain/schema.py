from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field


class DocumentType(StrEnum):
    note = "note"
    meeting = "meeting"
    article = "article"
    book = "book"
    journal = "journal"


class DocumentMeta(BaseModel):
    title: str
    date: date
    type: DocumentType
    tags: list[str] = Field(default_factory=list)
    author: str | None = None
    source: str | None = None


class BrainDocument(BaseModel):
    meta: DocumentMeta
    content: str
    source_path: str | None = None
