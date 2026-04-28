import os
import tempfile

from brain.config import BrainConfig


def test_config_defaults():
    cfg = BrainConfig()
    assert cfg.ollama_url == "http://localhost:11434"
    assert cfg.chat_model == "gemma4:e4b"
    assert cfg.embed_model == "nomic-embed-text"
    assert cfg.db_path.endswith("brain.db")
    assert cfg.chunk_size == 512
    assert cfg.chunk_overlap == 50
    assert cfg.retrieval_fetch_k == 40
    assert cfg.retrieval_top_k == 8
    assert cfg.retrieval_mmr_lambda == 0.7
    assert cfg.retrieval_max_context_chars == 12000
    assert cfg.retrieval_max_best_distance == 500.0
    assert cfg.retrieval_relative_distance_margin == 0.8


def test_config_loads_from_toml():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.toml")
        with open(config_path, "w") as f:
            f.write('ollama_url = "http://other:11434"\nchat_model = "llama3"\nchunk_size = 1024\n')
        cfg = BrainConfig.load_from(config_path)
        assert cfg.ollama_url == "http://other:11434"
        assert cfg.chat_model == "llama3"
        assert cfg.embed_model == "nomic-embed-text"  # default
        assert cfg.chunk_size == 1024


def test_agent_config_defaults():
    cfg = BrainConfig()
    assert cfg.agent.system_prompt != ""
    assert cfg.agent.tone == "helpful and concise"
    assert cfg.agent.goals == "Help the user retrieve information from their knowledge base"


def test_agent_config_loads_from_toml():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.toml")
        with open(config_path, "w") as f:
            f.write(
                "[agent]\n"
                'system_prompt = "You are a pirate."\n'
                'tone = "gruff"\n'
                'goals = "Find treasure"\n'
            )
        cfg = BrainConfig.load_from(config_path)
        assert cfg.agent.system_prompt == "You are a pirate."
        assert cfg.agent.tone == "gruff"
        assert cfg.agent.goals == "Find treasure"
