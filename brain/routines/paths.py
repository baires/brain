from __future__ import annotations

import os
from pathlib import Path

from brain.config import BrainConfig


def state_db_path(cfg: BrainConfig) -> Path:
    db_dir = cfg.db_path
    if db_dir.endswith(".db"):
        db_dir = os.path.dirname(db_dir)
    return Path(db_dir) / "state.db"
