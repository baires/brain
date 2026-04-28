import os
import tempfile

import boto3
from moto import mock_aws
from typer.testing import CliRunner

from brain.cli import app
from brain.remote import RemoteConfig

runner = CliRunner()


class _FakeProvider:
    def embed(self, text, model):
        return [0.1] * 384

    def chat(self, prompt, model, system=None):
        yield ""


@mock_aws
def test_s3_sync_ingests_new_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        from pathlib import Path

        import brain.commands.init as init_mod
        import brain.config as config_mod

        orig_default = config_mod.DEFAULT_CONFIG_PATH
        config_mod.DEFAULT_CONFIG_PATH = Path(os.path.join(tmpdir, ".brain", "config.toml"))
        orig_init_dir = init_mod.DEFAULT_CONFIG_DIR
        init_mod.DEFAULT_CONFIG_DIR = Path(os.path.join(tmpdir, ".brain"))

        import brain.commands.sync_s3 as sync_mod
        import brain.sources.s3 as s3_mod

        orig_get_provider = sync_mod.get_provider
        sync_mod.get_provider = lambda cfg: _FakeProvider()

        state_path = os.path.join(tmpdir, "s3_state.db")

        try:
            runner.invoke(app, ["init"])

            conn = boto3.resource("s3", region_name="us-east-1")
            conn.create_bucket(Bucket="brain-bucket")
            conn.Object("brain-bucket", "note1.md").put(
                Body=b"---\ntitle: S3 Note\ndate: 2026-04-26\ntype: note\n---\nS3 content."
            )

            from brain.sources.s3 import S3Source

            source = S3Source(state_db_path=state_path)

            objects = source.list_objects("brain-bucket")
            assert len(objects) == 1
            assert objects[0]["key"] == "note1.md"

            text = source.download_object("brain-bucket", "note1.md")
            assert "S3 content" in text

            s3_mod.S3Source.__init__.__defaults__ = (state_path, None, None, None)

            remote = RemoteConfig(
                name="test",
                bucket="brain-bucket",
                prefix="",
                endpoint="https://s3.amazonaws.com",
                key_id=None,
                secret=None,
            )

            sync_mod.run_sync_s3(remote)

            import sys
            from io import StringIO

            captured = StringIO()
            old_stdout = sys.stdout
            sys.stdout = captured
            try:
                sync_mod.run_sync_s3(remote)
            finally:
                sys.stdout = old_stdout
            assert "no new" in captured.getvalue().lower()

        finally:
            config_mod.DEFAULT_CONFIG_PATH = orig_default
            init_mod.DEFAULT_CONFIG_DIR = orig_init_dir
            sync_mod.get_provider = orig_get_provider
            s3_mod.S3Source.__init__.__defaults__ = (None, None, None, None)
