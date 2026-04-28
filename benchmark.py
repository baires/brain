#!/usr/bin/env python3
"""
Benchmark: master vs current branch RAG implementation.

Usage:
    uv run python benchmark.py [--notes-dir notes-demo] [--with-expansion]

How it works:
- Creates a temporary git worktree pointing at master
- Runs the benchmark worker (--worker mode) as a subprocess from each worktree
- Each worker ingests notes into its own temp ChromaDB, runs all eval questions, outputs JSON
- The main process diffs the two JSON result sets and prints a report

The production DB (~/.brain/brain.db) is never touched.
Chunks are isolated per-run via tempfile.TemporaryDirectory.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


# ── Ground-truth eval set ──────────────────────────────────────────────────────

CASES = [
    {
        "question": "What are the action items from the Acme sales meeting?",
        "expected_terms": ["Bob", "proposal", "Carol", "Alice", "legal"],
        "expected_source": "acme",
    },
    {
        "question": "What is Marcus blocked on?",
        "expected_terms": ["staging", "OAuth"],
        "expected_source": "standup",
    },
    {
        "question": "What was the Acme deal value?",
        "expected_terms": ["240K", "ARR"],
        "expected_source": "acme",
    },
    {
        "question": "What engineering work is planned for today?",
        "expected_terms": ["webhook", "retry", "migration"],
        "expected_source": "standup",
    },
    {
        "question": "Who are the attendees of the sales meeting?",
        "expected_terms": ["Alice", "Bob", "Carol", "Dave"],
        "expected_source": "acme",
    },
    {
        "question": "What are the key decisions from the product meeting?",
        "expected_terms": ["decision"],
        "expected_source": "product",
    },
    {
        "question": "What book notes do we have on habits?",
        "expected_terms": ["habit"],
        "expected_source": "atomic",
    },
]


# ── Result types ───────────────────────────────────────────────────────────────

@dataclass
class CaseResult:
    question: str
    answer: str
    latency_s: float
    retrieved_sources: list[str]
    correct_source_retrieved: bool
    has_citation: bool
    found_terms: list[str]
    missing_terms: list[str]
    context_chars_used: int
    num_results: int

    @property
    def term_coverage(self) -> float:
        total = len(self.found_terms) + len(self.missing_terms)
        return len(self.found_terms) / total if total else 0.0

    @property
    def passed(self) -> bool:
        return self.correct_source_retrieved and self.has_citation and self.term_coverage >= 0.5


@dataclass
class BenchmarkResult:
    label: str
    cases: list[CaseResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return sum(1 for c in self.cases if c.passed) / len(self.cases) if self.cases else 0.0

    @property
    def avg_latency(self) -> float:
        return sum(c.latency_s for c in self.cases) / len(self.cases) if self.cases else 0.0

    @property
    def avg_term_coverage(self) -> float:
        return sum(c.term_coverage for c in self.cases) / len(self.cases) if self.cases else 0.0

    @property
    def citation_rate(self) -> float:
        return sum(1 for c in self.cases if c.has_citation) / len(self.cases) if self.cases else 0.0

    @property
    def source_recall(self) -> float:
        return sum(1 for c in self.cases if c.correct_source_retrieved) / len(self.cases) if self.cases else 0.0


# ── Worker (runs inside a specific worktree) ───────────────────────────────────

def _worker_main(notes_dir: str, query_expansion: bool) -> None:
    """Ingest notes into a temp DB, run all eval cases, print JSON to stdout."""
    from brain.config import BrainConfig
    from brain.ingest import ingest_document
    from brain.ollama import OllamaClient
    from brain.parser import ParseError, parse_document
    from brain.query import QueryEngine
    from brain.store import BrainStore

    cfg = BrainConfig.load_from()
    notes_path = Path(notes_dir).resolve()
    notes_parent = notes_path.parent
    md_files = sorted(notes_path.glob("**/*.md"))

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "bench.db")
        store = BrainStore(db_path=db_path)
        ollama = OllamaClient(base_url=cfg.ollama_url)

        for md_file in md_files:
            try:
                raw = md_file.read_text(encoding="utf-8")
                rel_path = str(md_file.relative_to(notes_parent))
                doc = parse_document(raw, source_path=rel_path)
                ingest_document(
                    doc, store, ollama,
                    embed_model=cfg.embed_model,
                    chunk_size=cfg.chunk_size,
                    chunk_overlap=cfg.chunk_overlap,
                )
            except (ParseError, UnicodeDecodeError):
                pass

        # Build engine — handle branches that don't have query_expansion param yet
        try:
            engine = QueryEngine(
                store=store,
                ollama=ollama,
                embed_model=cfg.embed_model,
                chat_model=cfg.chat_model,
                fetch_k=cfg.retrieval_fetch_k,
                top_k=cfg.retrieval_top_k,
                mmr_lambda=cfg.retrieval_mmr_lambda,
                max_context_chars=cfg.retrieval_max_context_chars,
                max_best_distance=cfg.retrieval_max_best_distance,
                relative_distance_margin=cfg.retrieval_relative_distance_margin,
                system_prompt=cfg.agent.system_prompt,
                query_expansion=query_expansion,
            )
        except TypeError:
            # master branch QueryEngine doesn't have query_expansion param
            engine = QueryEngine(
                store=store,
                ollama=ollama,
                embed_model=cfg.embed_model,
                chat_model=cfg.chat_model,
                fetch_k=cfg.retrieval_fetch_k,
                top_k=cfg.retrieval_top_k,
                mmr_lambda=cfg.retrieval_mmr_lambda,
                max_context_chars=cfg.retrieval_max_context_chars,
                max_best_distance=cfg.retrieval_max_best_distance,
                relative_distance_margin=cfg.retrieval_relative_distance_margin,
                system_prompt=cfg.agent.system_prompt,
            )

        results = []
        for case in CASES:
            question = case["question"]
            expected_terms = case["expected_terms"]
            expected_source = case["expected_source"]

            t0 = time.perf_counter()
            retrieved = engine.retrieve(question)
            context = engine.build_context(retrieved)
            prompt = engine.build_prompt(question, context)
            tokens = list(engine.ollama.chat(
                prompt=prompt,
                model=engine.chat_model,
                system=engine.system_prompt,
            ))
            latency = time.perf_counter() - t0

            answer = "".join(tokens).strip()
            retrieved_sources = [r.source_path for r in retrieved]
            correct_source = any(expected_source in src for src in retrieved_sources)
            has_citation = "[" in answer and "]" in answer
            found = [t for t in expected_terms if t.lower() in answer.lower()]
            missing = [t for t in expected_terms if t.lower() not in answer.lower()]
            context_chars = sum(len(r.text) for r in retrieved)

            results.append({
                "question": question,
                "answer": answer,
                "latency_s": latency,
                "retrieved_sources": retrieved_sources,
                "correct_source_retrieved": correct_source,
                "has_citation": has_citation,
                "found_terms": found,
                "missing_terms": missing,
                "context_chars_used": context_chars,
                "num_results": len(retrieved),
            })

        print(json.dumps(results))


# ── Subprocess runner ──────────────────────────────────────────────────────────

def _run_worker_in(worktree_path: str, notes_dir_abs: str, query_expansion: bool) -> list[dict]:
    """Run the benchmark worker as a subprocess from a given worktree directory."""
    env = os.environ.copy()
    # Ensure the worktree's source is importable
    env["PYTHONPATH"] = worktree_path

    cmd = [
        sys.executable, str(Path(worktree_path) / "benchmark.py"),
        "--_worker", notes_dir_abs,
        "--_expansion", str(query_expansion),
    ]
    result = subprocess.run(
        cmd,
        cwd=worktree_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        print(f"Worker failed (exit {result.returncode}):\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    # The worker emits JSON as the last line (uv may print warnings before it)
    for line in reversed(result.stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("["):
            return json.loads(line)
    print(f"No JSON found in worker output:\n{result.stdout}", file=sys.stderr)
    sys.exit(1)


def _load_result(label: str, raw: list[dict]) -> BenchmarkResult:
    br = BenchmarkResult(label=label)
    for r in raw:
        br.cases.append(CaseResult(**r))
    return br


# ── Report ─────────────────────────────────────────────────────────────────────

def print_report(old: BenchmarkResult, new: BenchmarkResult) -> None:
    print(f"\n{'═' * 70}")
    print(f"  BENCHMARK: {old.label}  →  {new.label}")
    print(f"{'═' * 70}")
    print(f"  {'Metric':<30} {'Old':>10} {'New':>10} {'Delta':>10}")
    print(f"  {'─' * 60}")

    def fmt_delta_pct(ov: float, nv: float, higher_better: bool) -> str:
        diff = nv - ov
        if abs(diff) < 0.005:
            return "  ─"
        better = (diff > 0) == higher_better
        arrow = "▲" if better else "▼"
        return f"{arrow} {abs(diff):.1%}"

    metrics = [
        ("Pass rate",       old.pass_rate,        new.pass_rate,        True),
        ("Source recall",   old.source_recall,    new.source_recall,    True),
        ("Citation rate",   old.citation_rate,    new.citation_rate,    True),
        ("Term coverage",   old.avg_term_coverage, new.avg_term_coverage, True),
    ]
    for name, ov, nv, hb in metrics:
        d = fmt_delta_pct(ov, nv, hb)
        print(f"  {name:<30} {ov:>10.1%} {nv:>10.1%} {d:>10}")

    # Latency
    ov, nv = old.avg_latency, new.avg_latency
    diff = nv - ov
    arrow = "▲" if diff > 0 else "▼"
    d = f"{arrow} {abs(diff):.1f}s" if abs(diff) > 0.1 else "  ─"
    print(f"  {'Avg latency (s)':<30} {ov:>10.1f} {nv:>10.1f} {d:>10}")

    print(f"\n  {'Q':>3}  {'Src':>4}  {'Cite':>4}  {'Cov%':>5}  {'Old✓':>5}  {'New✓':>5}  Question")
    print(f"  {'─' * 70}")
    for i, (oc, nc) in enumerate(zip(old.cases, new.cases), 1):
        src = "✓" if nc.correct_source_retrieved else "✗"
        cit = "✓" if nc.has_citation else "✗"
        cov = f"{nc.term_coverage:.0%}"
        op = "✓" if oc.passed else "✗"
        np_ = "✓" if nc.passed else "✗"
        changed = " ←" if oc.passed != nc.passed else ""
        print(f"  {i:>3}  {src:>4}  {cit:>4}  {cov:>5}  {op:>5}  {np_:>5}  {nc.question[:40]}{changed}")

    print(f"\n  Answers (new branch):")
    for i, nc in enumerate(new.cases, 1):
        oc = old.cases[i - 1]
        print(f"\n  Q{i}: {nc.question}")
        print(f"  OLD: {oc.answer[:180]}{'...' if len(oc.answer) > 180 else ''}")
        print(f"  NEW: {nc.answer[:180]}{'...' if len(nc.answer) > 180 else ''}")

    print(f"\n{'═' * 70}\n")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--notes-dir", default="notes-demo")
    parser.add_argument("--with-expansion", action="store_true")
    # Internal worker flags — used when this script is invoked as a subprocess
    parser.add_argument("--_worker", metavar="NOTES_DIR", help=argparse.SUPPRESS)
    parser.add_argument("--_expansion", default="False", help=argparse.SUPPRESS)
    args = parser.parse_args()

    # Worker mode: ingest + run + print JSON, then exit
    if args._worker:
        _worker_main(args._worker, args._expansion.lower() == "true")
        return

    # Resolve paths before creating worktree (relative paths break after chdir)
    repo_root = Path(__file__).parent.resolve()
    notes_dir_abs = str((repo_root / args.notes_dir).resolve())

    if not Path(notes_dir_abs).exists():
        print(f"Notes directory not found: {notes_dir_abs}", file=sys.stderr)
        sys.exit(1)

    # Determine current branch
    current_branch = subprocess.check_output(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=repo_root, text=True
    ).strip()

    print(f"\nBenchmarking:  master  →  {current_branch}")
    print(f"Notes source:  {args.notes_dir}/")
    print(f"Query expansion (new): {args.with_expansion}")

    with tempfile.TemporaryDirectory() as wt_dir:
        wt_path = str(Path(wt_dir) / "master-wt")

        print(f"\n[1/2] Creating temporary worktree for master at {wt_path}...")
        subprocess.run(
            ["git", "worktree", "add", "--detach", wt_path, "master"],
            cwd=repo_root, check=True, capture_output=True
        )

        # Copy benchmark.py into the master worktree so it can self-invoke as worker
        import shutil
        shutil.copy(str(repo_root / "benchmark.py"), str(Path(wt_path) / "benchmark.py"))

        try:
            print("[1/2] Running master branch...")
            old_raw = _run_worker_in(wt_path, notes_dir_abs, query_expansion=False)
            old_result = _load_result("master", old_raw)

            print(f"\n[2/2] Running {current_branch} branch...")
            new_raw = _run_worker_in(str(repo_root), notes_dir_abs, query_expansion=args.with_expansion)
            new_result = _load_result(f"{current_branch} (expansion={args.with_expansion})", new_raw)

        finally:
            subprocess.run(
                ["git", "worktree", "remove", "--force", wt_path],
                cwd=repo_root, capture_output=True
            )

        print_report(old_result, new_result)


if __name__ == "__main__":
    main()
