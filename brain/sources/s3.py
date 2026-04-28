import sqlite3
from datetime import datetime

import boto3


class S3Source:
    def __init__(
        self,
        state_db_path: str | None = None,
        endpoint_url: str | None = None,
        key_id: str | None = None,
        secret: str | None = None,
    ):
        self.state_db_path = state_db_path or str(
            __import__("pathlib").Path.home() / ".brain" / "s3_state.db"
        )
        self._endpoint_url = endpoint_url
        self._key_id = key_id
        self._secret = secret
        self._init_db()

    def _boto3_client(self):
        kwargs = {}
        if self._endpoint_url:
            kwargs["endpoint_url"] = self._endpoint_url
        if self._key_id and self._secret:
            kwargs["aws_access_key_id"] = self._key_id
            kwargs["aws_secret_access_key"] = self._secret
        return boto3.client("s3", **kwargs)

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.state_db_path)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS s3_state (
                bucket TEXT NOT NULL,
                key TEXT NOT NULL,
                etag TEXT NOT NULL,
                ingested_at TEXT NOT NULL,
                PRIMARY KEY (bucket, key)
            )
            """
        )
        conn.commit()
        conn.close()

    def list_objects(self, bucket: str, prefix: str = "") -> list[dict]:
        s3 = self._boto3_client()
        kwargs = {"Bucket": bucket}
        if prefix:
            kwargs["Prefix"] = prefix
        response = s3.list_objects_v2(**kwargs)
        objects = []
        for obj in response.get("Contents", []):
            key = obj["Key"]
            if key.endswith("/"):
                continue
            objects.append(
                {
                    "key": key,
                    "etag": obj["ETag"].strip('"'),
                    "size": obj["Size"],
                }
            )
        return objects

    def download_object(self, bucket: str, key: str) -> str:
        s3 = self._boto3_client()
        response = s3.get_object(Bucket=bucket, Key=key)
        return response["Body"].read().decode("utf-8")

    def get_known_etags(self, bucket: str) -> dict:
        conn = sqlite3.connect(self.state_db_path)
        cursor = conn.execute("SELECT key, etag FROM s3_state WHERE bucket = ?", (bucket,))
        rows = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()
        return rows

    def mark_ingested(self, bucket: str, key: str, etag: str) -> None:
        conn = sqlite3.connect(self.state_db_path)
        conn.execute(
            """
            INSERT OR REPLACE INTO s3_state (bucket, key, etag, ingested_at)
            VALUES (?, ?, ?, ?)
            """,
            (bucket, key, etag, datetime.utcnow().isoformat()),
        )
        conn.commit()
        conn.close()
