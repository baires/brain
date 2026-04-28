from brain.config import BrainConfig
from brain.store import BrainStore


def run_status() -> None:
    cfg = BrainConfig.load_from()
    store = BrainStore(db_path=cfg.db_path)
    count = store.count()
    print(f"Documents: {count}")
    print(f"DB path: {cfg.db_path}")
    print(f"Chat model: {cfg.chat_model}")
    print(f"Embed model: {cfg.embed_model}")
