from pathlib import Path

import typer

from brain.backup import BackupEngine
from brain.config import BrainConfig
from brain.routines.events import emit


def run_backup(list_flag: bool = False, restore_path: str | None = None) -> None:
    cfg = BrainConfig.load_from()
    engine = BackupEngine(cfg)

    if list_flag:
        backups = engine.list_backups()
        if not backups:
            typer.echo("No backups found.")
            return
        typer.echo(f"{'Timestamp':<25} {'Size':>10}  Path")
        for b in backups:
            ts = b["timestamp"]
            size = b["size"]
            path = b["path"]
            typer.echo(f"{ts:<25} {size:>10}  {path}")
        return

    if restore_path:
        try:
            engine.restore_backup(restore_path)
            typer.echo(f"Restored from {restore_path}")
        except Exception as exc:
            typer.echo(f"Restore failed: {exc}", err=True)
            raise typer.Exit(1) from None
        return

    # Default: create backup
    db_path = Path(cfg.db_path).expanduser()
    if not db_path.exists():
        typer.echo(
            f"No database found at {db_path}. Run 'brain init' and ingest some documents first."
        )
        raise typer.Exit(1)
    try:
        path = engine.create_backup()
        typer.echo(f"Backup created: {path}")
        emit("on_backup", path=str(path))
    except Exception as exc:
        typer.echo(f"Backup failed: {exc}", err=True)
        raise typer.Exit(1) from None
