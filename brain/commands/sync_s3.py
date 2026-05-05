from brain.config import BrainConfig
from brain.ingest import ingest_document
from brain.parser import ParseError, parse_document
from brain.providers import get_embedder
from brain.remote import RemoteConfig
from brain.sources.s3 import S3Source
from brain.store import BrainStore


def run_sync_s3(remote: RemoteConfig) -> None:
    cfg = BrainConfig.load_from()
    store = BrainStore(db_path=cfg.db_path)
    embedder = get_embedder(cfg)
    source = S3Source(
        endpoint_url=remote.endpoint,
        key_id=remote.key_id,
        secret=remote.secret,
    )

    objects = source.list_objects(remote.bucket, prefix=remote.prefix)
    known = source.get_known_etags(remote.bucket)

    new_or_changed = []
    for obj in objects:
        key = obj["key"]
        etag = obj["etag"]
        if known.get(key) == etag:
            continue
        new_or_changed.append(obj)

    if not new_or_changed:
        print("No new or changed files. Everything up to date.")
        return

    ingested = 0
    for obj in new_or_changed:
        key = obj["key"]
        try:
            raw = source.download_object(remote.bucket, key)
            doc = parse_document(raw, source_path=f"s3://{remote.bucket}/{key}")
        except (ParseError, UnicodeDecodeError) as e:
            print(f"Skipped s3://{remote.bucket}/{key}: {e}")
            continue

        chunk_count = ingest_document(
            doc,
            store,
            embedder,
            embed_model=cfg.embed_model,
            chunk_size=cfg.chunk_size,
            chunk_overlap=cfg.chunk_overlap,
        )
        if not chunk_count:
            continue
        source.mark_ingested(remote.bucket, key, obj["etag"])
        ingested += 1
        print(f"Ingested s3://{remote.bucket}/{key} ({chunk_count} chunks)")

    print(f"Done. Ingested {ingested}/{len(new_or_changed)} new/changed files.")
