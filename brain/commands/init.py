from pathlib import Path

from brain.backup import get_or_create_backup_key
from brain.config import BrainConfig

DEFAULT_CONFIG_DIR = Path.home() / ".brain"


def run_init() -> None:
    config_dir = Path(DEFAULT_CONFIG_DIR)
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.toml"
    if not config_path.exists():
        default = BrainConfig()
        db_path = str(config_dir / "brain.db")
        lines = [
            f'ollama_url = "{default.ollama_url}"',
            f'chat_model = "{default.chat_model}"',
            f'embed_model = "{default.embed_model}"',
            f'db_path = "{db_path}"',
            f"chunk_size = {default.chunk_size}",
            f"chunk_overlap = {default.chunk_overlap}",
            f"retrieval_fetch_k = {default.retrieval_fetch_k}",
            f"retrieval_top_k = {default.retrieval_top_k}",
            f"retrieval_mmr_lambda = {default.retrieval_mmr_lambda}",
            f"retrieval_max_context_chars = {default.retrieval_max_context_chars}",
            f"retrieval_max_best_distance = {default.retrieval_max_best_distance}",
            f"retrieval_relative_distance_margin = {default.retrieval_relative_distance_margin}",
        ]
        config_path.write_text("\n".join(lines) + "\n")

    # Set up backup encryption key (idempotent)
    try:
        _, phrase = get_or_create_backup_key()
        if phrase:
            print(f"Initialized brain at {config_dir}")
            _print_passphrase(phrase)
            return
    except Exception:
        # Gracefully skip if keyring is unavailable
        pass

    print(f"Initialized brain at {config_dir}")


def _print_passphrase(phrase: str) -> None:
    width = 64
    border = "═" * width
    words = phrase.split()
    line1 = " ".join(words[:6])
    line2 = " ".join(words[6:])

    print()
    print(f"╔{border}╗")
    print(f"║{'🔐  BACKUP RECOVERY PASSPHRASE':^{width}}║")
    print(f"╠{border}╣")
    print(f"║{'Write these 12 words down and store them somewhere safe.':^{width}}║")
    print(f"║{'ONLY way to recover backups if your keyring is ever reset.':^{width}}║")
    print(f"╠{border}╣")
    print(f"║{line1:^{width}}║")
    print(f"║{line2:^{width}}║")
    print(f"╚{border}╝")
    print()
