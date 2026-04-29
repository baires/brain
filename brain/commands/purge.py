import shutil
from pathlib import Path

import typer


def run_purge(db_path: str) -> None:
    path = Path(db_path)
    if not path.exists():
        typer.echo("Nothing to purge — DB does not exist.")
        return

    typer.echo("")
    typer.echo("⚠️  WARNING: This will permanently delete your entire brain database.")
    typer.echo(f"   Path: {path}")
    typer.echo("   All ingested notes and embeddings will be lost.")
    typer.echo("   This cannot be undone.")
    typer.echo("")

    confirmed = typer.confirm("Type 'yes' to confirm — are you sure?")
    if not confirmed:
        typer.echo("Aborted.")
        raise typer.Exit(0)

    shutil.rmtree(path)
    typer.echo(f"Purged. {path} has been deleted.")
