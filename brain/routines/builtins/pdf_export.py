from pathlib import Path

from brain.routines.models import (
    RoutineAction,
    RoutineContext,
    RoutineResult,
)
from brain.routines.registry import register_builtin


def _sanitize_for_pdf(text: str) -> str:
    """Replace common unicode characters with ASCII equivalents for fpdf2."""
    replacements = {
        "\u2014": "-",  # em dash
        "\u2013": "-",  # en dash
        "\u2018": "'",  # left single quote
        "\u2019": "'",  # right single quote
        "\u201c": '"',  # left double quote
        "\u201d": '"',  # right double quote
        "\u2026": "...",  # ellipsis
        "\u00a0": " ",  # non-breaking space
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _build_html(title: str, body: str, results: list[dict]) -> str:
    """Build HTML content for fpdf2 write_html."""
    parts = [f"<h1>{_escape_html(title)}</h1>"]

    if body:
        parts.append(f"<p>{_escape_html(body)}</p>")

    if not results:
        parts.append("<p><i>No matching notes found.</i></p>")
        return "\n".join(parts)

    for i, r in enumerate(results, 1):
        meta = r.get("metadata", {})
        note_title = meta.get("title", "Untitled")
        source = meta.get("source_path", "")
        date = meta.get("date", "")
        doc_type = meta.get("doc_type", "")
        text = r.get("text", "").strip()

        header = f"{i}. {_escape_html(note_title)}"
        if doc_type:
            header += f" ({_escape_html(doc_type)})"
        if date:
            header += f" - {_escape_html(date)}"
        parts.append(f"<h2>{header}</h2>")

        if source:
            parts.append(f"<p><i>{_escape_html(source)}</i></p>")

        if text:
            snippet = text[:1000] + "..." if len(text) > 1000 else text
            parts.append(f"<p>{_escape_html(snippet)}</p>")

    return "\n".join(parts)


def _escape_html(text: str) -> str:
    """Minimal HTML escaping for fpdf2."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


@register_builtin
class PdfExportAction(RoutineAction):
    name = "pdf_export"

    def run(self, context: RoutineContext, params: dict) -> RoutineResult:
        output_path = params.get("output_path")
        if not output_path:
            return RoutineResult(success=False, message="Missing 'output_path' parameter")

        title = params.get("title", f"Brain Export - {context.routine_name}")
        body = params.get("body", "")

        query = params.get("query") or context.query
        results: list[dict] = []
        if query:
            try:
                results = context.search(query, n_results=params.get("n_results", 20))
            except Exception as exc:
                return RoutineResult(
                    success=False,
                    message=f"Query failed for routine '{context.routine_name}': {exc}",
                )

        if not body and not results:
            body = f"Routine '{context.routine_name}' generated this PDF."

        html = _build_html(title, body, results)
        html = _sanitize_for_pdf(html)

        try:
            from fpdf import FPDF
        except ImportError:
            return RoutineResult(
                success=False,
                message="fpdf2 is required for PDF export. Install with: uv pip install fpdf2",
            )

        pdf = FPDF()
        pdf.add_page()
        pdf.write_html(html)

        path = Path(output_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        pdf.output(str(path))

        return RoutineResult(success=True, message=f"PDF written to {path}")
