from pathlib import Path

from brain.config import BrainConfig
from brain.ingest import ingest_document
from brain.ollama import OllamaClient
from brain.parser import ParseError, parse_document
from brain.routines.events import emit
from brain.store import BrainStore


def _collect_files(path: str) -> list[str]:
    files = []
    p = Path(path)
    if p.is_file():
        if p.suffix in (".md", ".txt"):
            files.append(str(p))
    elif p.is_dir():
        for f in p.rglob("*"):
            if f.is_file() and f.suffix in (".md", ".txt"):
                files.append(str(f))
    return files


def run_add(path: str) -> None:
    cfg = BrainConfig.load_from()
    store = BrainStore(db_path=cfg.db_path)
    ollama = OllamaClient(base_url=cfg.ollama_url)

    files = _collect_files(path)
    if not files:
        print(f"No .md or .txt files found at {path}")
        return

    ingested = 0
    for fpath in files:
        try:
            raw = Path(fpath).read_text(encoding="utf-8")
            doc = parse_document(raw, source_path=fpath)
        except (ParseError, UnicodeDecodeError) as e:
            print(f"Skipped {fpath}: {e}")
            continue

        chunk_count = ingest_document(
            doc,
            store,
            ollama,
            embed_model=cfg.embed_model,
            chunk_size=cfg.chunk_size,
            chunk_overlap=cfg.chunk_overlap,
        )
        if not chunk_count:
            continue
        ingested += 1
        print(f"Ingested {fpath} ({chunk_count} chunks)")

    print(f"Done. Ingested {ingested}/{len(files)} files.")
    emit("on_ingest", files_added=ingested, total_files=len(files))
