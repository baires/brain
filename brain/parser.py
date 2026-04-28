from datetime import date
from typing import Any

import yaml

from brain.schema import BrainDocument, DocumentMeta


class ParseError(ValueError):
    pass


def _coerce_dates(data: Any) -> Any:
    if isinstance(data, dict):
        return {k: _coerce_dates(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_coerce_dates(item) for item in data]
    if isinstance(data, date):
        return data.isoformat()
    return data


def parse_document(raw: str, source_path: str | None = None) -> BrainDocument:
    raw = raw.strip()
    if not raw.startswith("---"):
        raise ParseError("Document missing YAML frontmatter")

    parts = raw.split("---", 2)
    if len(parts) < 3:
        raise ParseError("Document missing YAML frontmatter end fence")

    frontmatter_raw = parts[1].strip()
    body = parts[2].strip()

    try:
        data = yaml.safe_load(frontmatter_raw) or {}
    except yaml.YAMLError as e:
        raise ParseError(f"Invalid YAML frontmatter: {e}") from e

    if not isinstance(data, dict):
        raise ParseError("Frontmatter is not a YAML mapping")

    try:
        meta = DocumentMeta(**data)
    except Exception as e:
        raise ParseError(f"Invalid document metadata: {e}") from e

    return BrainDocument(meta=meta, content=body, source_path=source_path)
