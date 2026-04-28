from unittest.mock import MagicMock, patch

from brain.sources.s3 import S3Source


def test_s3source_with_credentials_builds_client_with_them(tmp_path):
    with patch("brain.sources.s3.boto3.client") as mock_client:
        mock_client.return_value = MagicMock()
        source = S3Source(
            state_db_path=str(tmp_path / "state.db"),
            endpoint_url="https://r2.example.com",
            key_id="KEYID",
            secret="SECRET",
        )
        source.list_objects("bucket")

    mock_client.assert_called_once_with(
        "s3",
        endpoint_url="https://r2.example.com",
        aws_access_key_id="KEYID",
        aws_secret_access_key="SECRET",
    )


def test_s3source_without_credentials_uses_boto3_default_chain(tmp_path):
    with patch("brain.sources.s3.boto3.client") as mock_client:
        mock_client.return_value = MagicMock()
        source = S3Source(
            state_db_path=str(tmp_path / "state.db"),
            endpoint_url=None,
            key_id=None,
            secret=None,
        )
        source.list_objects("bucket")

    args, kwargs = mock_client.call_args
    assert "aws_access_key_id" not in kwargs
    assert "aws_secret_access_key" not in kwargs
