from __future__ import annotations

from pathlib import Path

import tomli
import tomli_w
from pydantic import BaseModel, Field

from brain.prompts import DEFAULT_SYSTEM_PROMPT

DEFAULT_CONFIG_PATH = Path.home() / ".brain" / "config.toml"


class AgentConfig(BaseModel):
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    tone: str = "helpful and concise"
    goals: str = "Help the user retrieve information from their knowledge base"


class BrainConfig(BaseModel):
    ollama_url: str = "http://localhost:11434"
    chat_model: str = "gemma4:e4b"
    embed_model: str = "nomic-embed-text"
    db_path: str = Field(default_factory=lambda: str(Path.home() / ".brain" / "brain.db"))
    chunk_size: int = 512
    chunk_overlap: int = 50
    retrieval_fetch_k: int = 40
    retrieval_top_k: int = 8
    retrieval_mmr_lambda: float = 0.7
    retrieval_max_context_tokens: int = 3000
    retrieval_max_best_distance: float = 500.0
    retrieval_relative_distance_margin: float = 0.8
    retrieval_query_expansion: bool = False
    backup_path: str = Field(default_factory=lambda: str(Path.home() / ".brain" / "backups"))
    backup_retention: int = 30
    backup_daily: bool = True
    agent: AgentConfig = Field(default_factory=AgentConfig)
    routines: list[RoutineConfig] = Field(default_factory=list)

    @classmethod
    def load_from(cls, path: str | Path | None = None) -> BrainConfig:
        path = Path(path) if path else DEFAULT_CONFIG_PATH
        defaults = cls().model_dump()
        if path.exists():
            with open(path, "rb") as f:
                data = tomli.load(f)
            defaults.update(data)
        return cls(**defaults)

    def save_to(self, path: str | Path | None = None) -> None:
        path = Path(path) if path else DEFAULT_CONFIG_PATH
        data = self.model_dump(exclude_none=True)
        with open(path, "wb") as f:
            tomli_w.dump(data, f)


# Resolve forward reference for routines field
from brain.routines.models import RoutineConfig  # noqa: E402

BrainConfig.model_rebuild()
