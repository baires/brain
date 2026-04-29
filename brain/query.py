import re
from collections.abc import Generator
from dataclasses import dataclass, field
from typing import Any

from brain.prompts import DEFAULT_SYSTEM_PROMPT
from brain.providers.base import EmbeddingProvider, LLMProvider, RerankerProvider, TokenizerProvider


@dataclass
class RetrievalResult:
    id: str
    text: str
    source_path: str = ""
    title: str = "Unknown"
    date: str = ""
    doc_type: str = ""
    author: str = ""
    source: str = ""
    breadcrumbs: list[str] = field(default_factory=list)
    distance: float = 0.0
    citation: int = 0
    embedding: list[float] | None = None
    lexical_score: float = 0.0


class QueryEngine:
    def __init__(
        self,
        store: Any,
        llm: LLMProvider,
        embedder: EmbeddingProvider,
        embed_model: str,
        chat_model: str,
        reranker: RerankerProvider | None = None,
        tokenizer: TokenizerProvider | None = None,
        fetch_k: int = 40,
        top_k: int = 8,
        mmr_lambda: float = 0.7,
        max_context_tokens: int = 3000,
        max_best_distance: float = 2.0,
        relative_distance_margin: float = 0.35,
        system_prompt: str | None = None,
        query_expansion: bool = False,
    ):
        self.store = store
        self.llm = llm
        self.embedder = embedder
        self.reranker = reranker
        self.tokenizer = tokenizer
        self.embed_model = embed_model
        self.chat_model = chat_model
        self.fetch_k = fetch_k
        self.top_k = top_k
        self.mmr_lambda = mmr_lambda
        self.max_context_tokens = max_context_tokens
        self.max_best_distance = max_best_distance
        self.relative_distance_margin = relative_distance_margin
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self.query_expansion = query_expansion

    def _expand_query(self, question: str) -> str:
        prompt = (
            "You are a search query generator. Rewrite the question into a highly effective keyword search query.\n"
            "Do NOT include any conversational text like 'Here is the query' or 'Search query:'.\n"
            "Output ONLY the keywords.\n\n"
            f"Question: {question}\n"
            "Query:"
        )
        tokens = list(self.llm.chat(prompt=prompt, model=self.chat_model))
        expanded = "".join(tokens).strip()
        # Clean up common model fluff just in case
        if "Here is" in expanded or "search query" in expanded.lower():
            expanded = expanded.split("\n")[-1].strip(" \"'")
        return expanded if expanded else question

    def retrieve(
        self,
        question: str,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievalResult]:
        query_text = self._expand_query(question) if self.query_expansion else question
        embedding = self.embedder.embed(query_text, model=self.embed_model)
        raw_results = self.store.query(
            embedding=embedding,
            filters=filters,
            n_results=self.fetch_k,
        )
        candidates = [self._to_retrieval_result(r) for r in raw_results]
        for candidate in candidates:
            candidate.lexical_score = self._lexical_score(question, candidate)
        candidates = self._filter_by_distance(candidates)
        if self.reranker:
            # If reranker is present, use it before MMR selection or replace MMR
            # Reranker returns indices mapped to scores
            rerank_results = self.reranker.rerank(
                question, [c.text for c in candidates], top_n=self.fetch_k
            )
            # Reorder candidates based on reranker
            candidates = [candidates[r["index"]] for r in rerank_results]

        candidates = self._select_mmr(candidates, self.top_k)
        candidates = self._apply_context_budget(candidates)
        for idx, result in enumerate(candidates, start=1):
            result.citation = idx
        return candidates

    def ask(
        self,
        question: str,
        filters: dict[str, Any] | None = None,
    ) -> Generator[str, None, None]:
        results = self.retrieve(question, filters=filters)
        if not results:
            yield "I don't know based on your notes."
            return
        context = self.build_context(results)
        prompt = self.build_prompt(question, context)
        yield from self.llm.chat(
            prompt=prompt,
            model=self.chat_model,
            system=self.system_prompt,
        )

    def build_context(self, results: list[RetrievalResult]) -> str:
        lines = ["<context>"]
        for r in results:
            section = " > ".join(r.breadcrumbs)
            source = f"{r.source_path}#{r.id.rsplit('#', 1)[-1]}" if r.source_path else r.id
            author_attr = f' author="{r.author}"' if r.author else ""
            lines.append(
                f'<document citation="{r.citation}" title="{r.title}" date="{r.date}" type="{r.doc_type}"'
                f'{author_attr} section="{section}" source="{source}">\n'
                f"{r.text}\n"
                f"</document>"
            )
        lines.append("</context>")
        return "\n".join(lines)

    def build_prompt(self, question: str, context: str) -> str:
        return (
            "Please answer the following question using ONLY the provided context documents.\n"
            "When you use information from a document, you MUST include its citation number in brackets, e.g., [1] or [2].\n\n"
            f"{context}\n\n"
            f"<question>\n{question}\n</question>\n\n"
            "Answer:"
        )

    # Backward-compatible aliases for tests/callers that used the old private names.
    def _build_context(self, results: list[Any]) -> str:
        converted = [
            r if isinstance(r, RetrievalResult) else self._to_retrieval_result(r) for r in results
        ]
        for idx, result in enumerate(converted, start=1):
            result.citation = result.citation or idx
        return self.build_context(converted)

    def _build_prompt(self, question: str, context: str) -> str:
        return self.build_prompt(question, context)

    def _to_retrieval_result(self, raw: dict[str, Any]) -> RetrievalResult:
        meta = raw.get("metadata", {}) or {}
        breadcrumbs = meta.get("breadcrumbs", "")
        if isinstance(breadcrumbs, str):
            breadcrumb_list = [part.strip() for part in breadcrumbs.split(">") if part.strip()]
        else:
            breadcrumb_list = list(breadcrumbs or [])
        return RetrievalResult(
            id=raw.get("id", ""),
            text=raw.get("text", ""),
            source_path=meta.get("source_path") or "",
            title=meta.get("title") or "Unknown",
            date=meta.get("date") or "",
            doc_type=meta.get("doc_type") or "",
            author=meta.get("author") or "",
            source=meta.get("source") or "",
            breadcrumbs=breadcrumb_list,
            distance=float(raw.get("distance", 0.0) or 0.0),
            embedding=raw.get("embedding"),
        )

    def _filter_by_distance(self, candidates: list[RetrievalResult]) -> list[RetrievalResult]:
        if not candidates:
            return []
        best = min(r.distance for r in candidates)
        if best > self.max_best_distance:
            return [r for r in candidates if r.lexical_score >= 2.0]
        cutoff = best * (1 + self.relative_distance_margin)
        return [r for r in candidates if r.distance <= cutoff or r.lexical_score >= 2.0]

    def _select_mmr(self, candidates: list[RetrievalResult], limit: int) -> list[RetrievalResult]:
        selected: list[RetrievalResult] = []
        remaining = sorted(candidates, key=self._rank_key)
        while remaining and len(selected) < limit:
            if not selected:
                selected.append(remaining.pop(0))
                continue
            best_idx = 0
            best_score = float("-inf")
            for idx, candidate in enumerate(remaining):
                relevance = self._relevance(candidate)
                duplicate_penalty = max(self._similarity(candidate, chosen) for chosen in selected)
                score = self.mmr_lambda * relevance - (1 - self.mmr_lambda) * duplicate_penalty
                if score > best_score:
                    best_score = score
                    best_idx = idx
            selected.append(remaining.pop(best_idx))
        return selected

    def _rank_key(self, result: RetrievalResult) -> tuple[float, float]:
        return (-self._relevance(result), result.distance)

    def _relevance(self, result: RetrievalResult) -> float:
        distance_score = 1 / (1 + result.distance)
        return distance_score + result.lexical_score

    def _similarity(self, a: RetrievalResult, b: RetrievalResult) -> float:
        if (
            a.embedding is not None
            and b.embedding is not None
            and len(a.embedding) == len(b.embedding)
        ):
            dot = sum(x * y for x, y in zip(a.embedding, b.embedding, strict=False))
            a_norm = sum(x * x for x in a.embedding) ** 0.5
            b_norm = sum(x * x for x in b.embedding) ** 0.5
            if a_norm and b_norm:
                return dot / (a_norm * b_norm)
        same_source = a.source_path and a.source_path == b.source_path
        same_section = a.breadcrumbs and a.breadcrumbs == b.breadcrumbs
        if same_source and same_section:
            return 1.0
        if same_source:
            return 0.7
        if same_section:
            return 0.4
        return 0.0

    def _lexical_score(self, question: str, result: RetrievalResult) -> float:
        query_terms = self._query_terms(question)
        if not query_terms:
            return 0.0
        haystack = " ".join(
            [
                result.title,
                result.doc_type,
                result.author,
                result.source,
                " ".join(result.breadcrumbs),
                result.text,
            ]
        ).lower()
        score = 0.0
        for term in query_terms:
            if term in haystack:
                score += 1.0
        title_lower = result.title.lower()
        for term in query_terms:
            if term in title_lower:
                score += 1.0
        return score

    def _query_terms(self, question: str) -> set[str]:
        terms = set(re.findall(r"[a-z0-9]+", question.lower()))
        stopwords = {
            "what",
            "are",
            "from",
            "last",
            "the",
            "a",
            "an",
            "of",
            "for",
            "to",
            "in",
            "on",
            "is",
            "was",
            "were",
            "did",
            "do",
            "does",
            "and",
            "or",
            "with",
            "how",
            "why",
            "when",
            "where",
            "who",
            "which",
            "about",
            "that",
            "this",
            "there",
            "then",
            "can",
            "could",
            "would",
            "should",
            "has",
            "have",
            "had",
        }
        return {term for term in terms if term not in stopwords and len(term) > 2}

    def _rendered_size(self, result: RetrievalResult) -> int:
        section = " > ".join(result.breadcrumbs)
        source = (
            f"{result.source_path}#{result.id.rsplit('#', 1)[-1]}"
            if result.source_path
            else result.id
        )
        header = (
            f'[{result.citation}] title="{result.title}" date="{result.date}" '
            f'type="{result.doc_type}" author="{result.author}" section="{section}" source="{source}"\n'
        )
        text = header + result.text
        if self.tokenizer:
            return self.tokenizer.count_tokens(text)
        # default naive char approximation to token count
        return len(text) // 4

    def _apply_context_budget(self, candidates: list[RetrievalResult]) -> list[RetrievalResult]:
        selected = []
        used = 0
        for candidate in candidates:
            projected = used + self._rendered_size(candidate)
            if selected and projected > self.max_context_tokens:
                break
            selected.append(candidate)
            used = projected
        return selected
