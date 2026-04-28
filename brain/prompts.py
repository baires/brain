DEFAULT_SYSTEM_PROMPT = (
    "You are a precise local-notes assistant. Answer using only the provided context. "
    "If the context does not answer the question, say: I don't know based on your notes. "
    "Always cite sources for factual claims using the citation number and source file path, "
    "for example [1: notes-demo/meeting.md]."
)


ANSWER_INSTRUCTIONS = (
    "Instructions:\n"
    "- Answer using only the cited context above.\n"
    "- Keep the answer concise.\n"
    "- Cite every factual claim with both citation number and source file path, "
    "for example [1: notes-demo/meeting.md].\n"
    '- Use the source="..." field from the cited context as the file path.\n'
    "- If the context does not answer the question, say: I don't know based on your notes."
)


STRUCTURE_TRANSCRIPT_SYSTEM_PROMPT = (
    "You structure raw local transcripts into factual markdown notes. "
    "Do not invent details. Preserve names, dates, decisions, blockers, and action items exactly when present."
)


def build_structure_transcript_prompt(
    *,
    title: str,
    doc_date: str,
    doc_type: str,
    tags: list[str] | None,
    author: str | None,
    raw_text: str,
) -> str:
    tag_text = ", ".join(tags or [])
    author_line = f"author: {author}" if author else ""
    return f"""Structure the raw transcript into a markdown document accepted by Brain.

Return only markdown. Do not wrap it in code fences. Do not add commentary.

Required YAML frontmatter:
---
title: "{title}"
date: {doc_date}
type: {doc_type}
tags: [{tag_text}]
source: transcript
{author_line}
---

Body requirements:
- Use clear markdown headings.
- Include sections when supported by the transcript: Summary, Participants, Key Decisions, Action Items, Blockers, Important Dates.
- Omit a section if the transcript does not support it.
- For action items, preserve owner names and concrete tasks.
- If a detail is not in the transcript, do not infer it.

Raw transcript:
{raw_text}
"""
