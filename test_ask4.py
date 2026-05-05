from brain.config import BrainConfig
from brain.providers import get_provider
from brain.query import QueryEngine
from brain.store import BrainStore

cfg = BrainConfig.load_from()
store = BrainStore(db_path=cfg.db_path)
provider = get_provider(cfg)
engine = QueryEngine(
    store=store,
    llm=provider,
    embedder=provider,
    embed_model=cfg.embed_model,
    chat_model=cfg.chat_model,
    fetch_k=cfg.retrieval_fetch_k,
    top_k=cfg.retrieval_top_k,
    mmr_lambda=cfg.retrieval_mmr_lambda,
    max_context_tokens=cfg.retrieval_max_context_tokens,
    max_best_distance=cfg.retrieval_max_best_distance,
    relative_distance_margin=cfg.retrieval_relative_distance_margin,
    system_prompt=cfg.agent.system_prompt,
    query_expansion=cfg.retrieval_query_expansion,
)

results = engine.retrieve("What is Marcus blocked on?")
context = engine.build_context(results)
print(context)
