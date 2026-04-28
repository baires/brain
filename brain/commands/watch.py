import os
import time

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from brain.config import BrainConfig
from brain.ingest import ingest_document
from brain.parser import ParseError, parse_document
from brain.providers import get_provider
from brain.sources.local import read_file
from brain.store import BrainStore


class _DebouncedHandler(FileSystemEventHandler):
    def __init__(self, debounce_seconds: float = 1.0):
        self.debounce_seconds = debounce_seconds
        self._last_event = 0.0

    def on_any_event(self, event):
        if event.is_directory:
            return
        if not event.src_path.endswith((".md", ".txt")):
            return
        now = time.time()
        if now - self._last_event < self.debounce_seconds:
            return
        self._last_event = now
        _process_file(event.src_path)


def _process_file(path: str) -> None:
    cfg = BrainConfig.load_from()
    store = BrainStore(db_path=cfg.db_path)
    llm = get_provider(cfg)

    try:
        raw = read_file(path)
        doc = parse_document(raw, source_path=path)
    except (ParseError, UnicodeDecodeError) as e:
        print(f"Skipped {path}: {e}")
        return

    chunk_count = ingest_document(
        doc,
        store,
        llm,
        embed_model=cfg.embed_model,
        chunk_size=cfg.chunk_size,
        chunk_overlap=cfg.chunk_overlap,
    )
    if not chunk_count:
        return
    print(f"Ingested {path} ({chunk_count} chunks)")


def run_watch(path: str) -> None:
    abs_path = os.path.abspath(path)
    handler = _DebouncedHandler(debounce_seconds=1.0)
    observer = Observer()
    observer.schedule(handler, abs_path, recursive=True)
    observer.start()
    print(f"Watching {abs_path} for changes... (Ctrl+C to stop)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
