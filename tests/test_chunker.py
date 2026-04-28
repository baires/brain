from brain.chunker import chunk_document
from brain.schema import BrainDocument, DocumentMeta, DocumentType


def _doc(content: str, title: str = "Test") -> BrainDocument:
    return BrainDocument(
        meta=DocumentMeta(title=title, date="2026-04-26", type=DocumentType.note),
        content=content,
        source_path="/tmp/test.md",
    )


def test_structured_markdown_chunks():
    content = """# Main Title

Intro paragraph here.

## Section One

Content for section one.
More content.

## Section Two

Content for section two.
"""
    doc = _doc(content)
    chunks = chunk_document(doc, chunk_size=500, chunk_overlap=20)
    assert len(chunks) >= 2
    # Breadcrumbs should include section headers
    section_one = [c for c in chunks if "Section One" in c.breadcrumbs]
    assert len(section_one) > 0
    assert "Content for section one" in section_one[0].text


def test_nested_markdown_breadcrumbs_preserved():
    content = """# Product Review

Intro.

## Decisions

Overview.

### Collaboration

- Use Operational Transform instead of CRDT.
- Defer presence indicators.
"""
    doc = _doc(content, title="Roadmap")
    chunks = chunk_document(doc, chunk_size=80, chunk_overlap=10)
    collaboration = [c for c in chunks if "Operational Transform" in c.text][0]
    assert collaboration.breadcrumbs == ["Roadmap", "Product Review", "Decisions", "Collaboration"]
    assert collaboration.meta.heading == "Collaboration"
    assert collaboration.meta.chunk_index >= 0


def test_unstructured_plain_text_chunks():
    content = "\n\n".join(
        [
            f"Paragraph {i} with enough text to be its own chunk that is quite long and detailed so it exceeds the small token limit."
            for i in range(5)
        ]
    )
    doc = _doc(content)
    chunks = chunk_document(doc, chunk_size=50, chunk_overlap=5)
    assert len(chunks) >= 2
    assert all(c.meta.source_path == "/tmp/test.md" for c in chunks)


def test_chunk_overlap_controls_repeated_boundary_text():
    content = "\n\n".join(
        [
            "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu",
            "nu xi omicron pi rho sigma tau upsilon phi chi psi omega",
        ]
    )
    doc = _doc(content)
    no_overlap = chunk_document(doc, chunk_size=20, chunk_overlap=0)
    with_overlap = chunk_document(doc, chunk_size=20, chunk_overlap=12)
    assert len(no_overlap) >= 2
    assert len(with_overlap) >= 2
    assert "lambda mu" not in no_overlap[1].text
    assert "lambda mu" in with_overlap[1].text


def test_chunk_respects_max_size():
    # approx 4 chars/token, so 256 tokens ~ 1024 chars
    long_para = "word " * 600  # ~3000 chars, should be split
    content = long_para
    doc = _doc(content)
    chunks = chunk_document(doc, chunk_size=256, chunk_overlap=20)
    for c in chunks:
        assert len(c.text) <= 256 * 4 + 100  # allow small margin


def test_chunk_ids_are_deterministic():
    content = "Some content here.\n\nMore content there."
    doc = _doc(content)
    chunks1 = chunk_document(doc, chunk_size=200, chunk_overlap=10)
    chunks2 = chunk_document(doc, chunk_size=200, chunk_overlap=10)
    assert [c.id for c in chunks1] == [c.id for c in chunks2]
