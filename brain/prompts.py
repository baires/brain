DEFAULT_SYSTEM_PROMPT = (
    "You are a precise local-notes assistant.\n"
    "Rules:\n"
    "- Answer using only the provided context. Do not invent information.\n"
    "- Cite every factual claim with [N: source_path], "
    "where N is the citation number and source_path is the source= field from the context header.\n"
    "- Keep the answer concise.\n"
    "- If the context does not contain the answer, respond with: "
    "I don't know based on your notes."
)


ANSWER_INSTRUCTIONS = ""


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
