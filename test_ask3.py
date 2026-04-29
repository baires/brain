import sys
from brain.config import BrainConfig
from brain.store import BrainStore

cfg = BrainConfig.load_from()
store = BrainStore(db_path=cfg.db_path)
raw = store.collection.get(where={"source_path": "notes-demo/2026-04-25-daily-standup.md"})
print(raw["metadatas"])
