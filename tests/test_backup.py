import os
from pathlib import Path
from unittest.mock import patch

import pytest

from brain.backup import (
    BackupEngine,
    _decode_words_to_seed,
    _encode_seed_to_words,
    _generate_backup_key,
    get_or_create_backup_key,
    recover_key_from_phrase,
)
from brain.config import BrainConfig


class TestAutoBackupHelper:
    def test_maybe_auto_backup_does_not_crash_on_corrupt_config(self, real_maybe_auto_backup):
        """_maybe_auto_backup in cli must not propagate exceptions from config loading."""
        with patch("brain.config.BrainConfig.load_from", side_effect=ValueError("corrupt config")):
            real_maybe_auto_backup()  # must not raise


class TestKeyManagement:
    def test_encode_decode_seed_roundtrip(self):
        seed = os.urandom(16)
        words = _encode_seed_to_words(seed)
        assert len(words) == 12
        assert all(word in words for word in words)
        recovered_seed = _decode_words_to_seed(" ".join(words))
        assert recovered_seed == seed

    def test_generate_backup_key(self):
        key, phrase = _generate_backup_key()
        assert len(key) == 44  # base64-urlsafe encoded 32 bytes
        words = phrase.split()
        assert len(words) == 12

    def test_recover_key_from_phrase(self):
        key, phrase = _generate_backup_key()
        recovered = recover_key_from_phrase(phrase)
        assert recovered == key

    @patch("brain.backup.keyring.get_password", return_value=None)
    @patch("brain.backup.keyring.set_password")
    def test_get_or_create_key_generates_new(self, mock_set, mock_get):
        key, phrase = get_or_create_backup_key()
        assert phrase is not None
        assert len(key) == 44
        mock_set.assert_called_once()

    @patch("brain.backup.keyring.get_password", return_value="test-key-string")
    @patch("brain.backup.keyring.set_password")
    def test_get_or_create_key_returns_existing(self, mock_set, mock_get):
        key, phrase = get_or_create_backup_key()
        assert phrase is None
        assert key == b"test-key-string"
        mock_set.assert_not_called()


class TestBackupEngine:
    @pytest.fixture
    def cfg(self, tmp_path):
        return BrainConfig(
            db_path=str(tmp_path / "brain.db"),
            backup_path=str(tmp_path / "backups"),
            backup_retention=3,
            backup_daily=False,
        )

    @pytest.fixture
    def fake_db(self, tmp_path):
        db = tmp_path / "brain.db"
        db.mkdir()
        (db / "chroma.sqlite3").write_text("fake db")
        return db

    def test_create_backup(self, cfg, fake_db):
        with patch(
            "brain.backup.get_or_create_backup_key",
            return_value=(b"JF3bfm6rkRTH8lTWEkQJEG6djZHOGsil2uhdbkcmglo=", None),
        ):
            engine = BackupEngine(cfg)
            path = engine.create_backup()

        assert path.exists()
        assert path.name.startswith("brain-backup-")
        assert path.suffixes == [".tar", ".gz", ".enc"]

    def test_restore_backup(self, cfg, fake_db):
        with patch(
            "brain.backup.get_or_create_backup_key",
            return_value=(b"JF3bfm6rkRTH8lTWEkQJEG6djZHOGsil2uhdbkcmglo=", None),
        ):
            engine = BackupEngine(cfg)
            backup_path = engine.create_backup()

            # Modify the DB
            (fake_db / "extra.txt").write_text("extra")

            # Restore
            engine.restore_backup(str(backup_path))

        assert fake_db.exists()
        assert not (fake_db / "extra.txt").exists()
        assert (fake_db / "chroma.sqlite3").read_text() == "fake db"
        # Old DB should be backed up
        assert any(Path(cfg.db_path).parent.glob("brain.db.bak.*"))

    def test_restore_backup_not_found(self, cfg, fake_db):
        engine = BackupEngine(cfg)
        with pytest.raises(FileNotFoundError):
            engine.restore_backup("/nonexistent/backup.tar.gz.enc")

    def test_list_backups(self, cfg, fake_db):
        with patch(
            "brain.backup.get_or_create_backup_key",
            return_value=(b"JF3bfm6rkRTH8lTWEkQJEG6djZHOGsil2uhdbkcmglo=", None),
        ):
            engine = BackupEngine(cfg)
            engine.create_backup()
            engine.create_backup()
            backups = engine.list_backups()

        assert len(backups) == 2
        assert all("path" in b and "timestamp" in b and "size" in b for b in backups)
        # Should be sorted by timestamp
        assert backups[0]["timestamp"] <= backups[1]["timestamp"]

    def test_enforce_retention(self, cfg, fake_db):
        with patch(
            "brain.backup.get_or_create_backup_key",
            return_value=(b"JF3bfm6rkRTH8lTWEkQJEG6djZHOGsil2uhdbkcmglo=", None),
        ):
            engine = BackupEngine(cfg)
            for _ in range(5):
                engine.create_backup()

        backups = list(Path(cfg.backup_path).glob("brain-backup-*.tar.gz.enc"))
        assert len(backups) == 3

    def test_maybe_trigger_backup_respects_daily(self, cfg, fake_db):
        with patch(
            "brain.backup.get_or_create_backup_key",
            return_value=(b"JF3bfm6rkRTH8lTWEkQJEG6djZHOGsil2uhdbkcmglo=", None),
        ):
            # backup_daily is False in fixture
            result = BackupEngine.maybe_trigger_backup(cfg)
        assert result is None

    def test_maybe_trigger_backup_creates_when_due(self, cfg, fake_db):
        cfg.backup_daily = True
        with patch(
            "brain.backup.get_or_create_backup_key",
            return_value=(b"JF3bfm6rkRTH8lTWEkQJEG6djZHOGsil2uhdbkcmglo=", None),
        ):
            result = BackupEngine.maybe_trigger_backup(cfg)
        assert result is not None
        assert result.exists()

    def test_maybe_trigger_backup_skips_when_recent(self, cfg, fake_db):
        cfg.backup_daily = True
        with patch(
            "brain.backup.get_or_create_backup_key",
            return_value=(b"JF3bfm6rkRTH8lTWEkQJEG6djZHOGsil2uhdbkcmglo=", None),
        ):
            engine = BackupEngine(cfg)
            engine.create_backup()  # creates a backup and updates timestamp
            result = BackupEngine.maybe_trigger_backup(cfg)
        assert result is None

    def test_restore_works_across_devices(self, cfg, fake_db):
        """restore_backup must work even when the extracted dir is on a different filesystem.

        shutil.move is used for the restored_db -> db_path step so it falls back to
        copy+delete instead of os.rename, which fails across devices.
        """
        import shutil as _shutil

        with patch(
            "brain.backup.get_or_create_backup_key",
            return_value=(b"JF3bfm6rkRTH8lTWEkQJEG6djZHOGsil2uhdbkcmglo=", None),
        ):
            engine = BackupEngine(cfg)
            backup_path = engine.create_backup()

            # Simulate cross-device by patching shutil.move to use copy+delete (not rename)
            cross_device_calls = []

            def copy_based_move(src, dst, *a, **kw):
                cross_device_calls.append((src, dst))
                # Emulate what shutil.move does when rename raises OSError(EXDEV)
                _shutil.copytree(src, dst) if Path(src).is_dir() else _shutil.copy2(src, dst)
                _shutil.rmtree(src) if Path(src).is_dir() else Path(src).unlink()

            with patch("brain.backup.shutil.move", side_effect=copy_based_move):
                engine.restore_backup(str(backup_path))

        assert fake_db.exists()
        assert (fake_db / "chroma.sqlite3").read_text() == "fake db"
        assert len(cross_device_calls) == 1

    def test_restore_validates_chroma_sqlite3_present(self, cfg, fake_db):
        """restore_backup must reject archives missing chroma.sqlite3."""
        with patch(
            "brain.backup.get_or_create_backup_key",
            return_value=(b"JF3bfm6rkRTH8lTWEkQJEG6djZHOGsil2uhdbkcmglo=", None),
        ):
            engine = BackupEngine(cfg)
            # Create a backup of a dir without chroma.sqlite3
            (fake_db / "chroma.sqlite3").unlink()
            (fake_db / "other_file.txt").write_text("not a chroma db")
            backup_path = engine.create_backup()

            with pytest.raises(ValueError, match="chroma.sqlite3"):
                engine.restore_backup(str(backup_path))

    def test_maybe_trigger_backup_prints_warning_on_failure(self, cfg, fake_db, capsys):
        """maybe_trigger_backup prints a warning when backup fails instead of silencing it."""
        cfg.backup_daily = True
        with patch(
            "brain.backup.get_or_create_backup_key", side_effect=RuntimeError("keyring unavailable")
        ):
            BackupEngine.maybe_trigger_backup(cfg)
        captured = capsys.readouterr()
        assert "warning" in captured.err.lower() or "backup" in captured.err.lower()

    def test_restore_shows_friendly_message_on_wrong_key(self, cfg, fake_db):
        """restore_backup raises ValueError with a friendly message on decryption failure."""
        with patch(
            "brain.backup.get_or_create_backup_key",
            return_value=(b"JF3bfm6rkRTH8lTWEkQJEG6djZHOGsil2uhdbkcmglo=", None),
        ):
            engine = BackupEngine(cfg)
            backup_path = engine.create_backup()

        # Now try to restore with a different key
        wrong_key = b"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
        with (
            patch("brain.backup.get_or_create_backup_key", return_value=(wrong_key, None)),
            pytest.raises(ValueError, match="[Cc]orrupted|wrong key"),
        ):
            engine.restore_backup(str(backup_path))
