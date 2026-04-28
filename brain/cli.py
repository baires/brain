import typer

from brain.commands.add import run_add
from brain.commands.ask import run_ask
from brain.commands.backup import run_backup
from brain.commands.chat import run_chat
from brain.commands.do import run_do
from brain.commands.eval import run_eval
from brain.commands.import_raw import run_import_raw
from brain.commands.init import run_init
from brain.commands.remote import run_remote_add, run_remote_list, run_remote_remove
from brain.commands.status import run_status
from brain.commands.sync_s3 import run_sync_s3
from brain.commands.watch import run_watch
from brain.remote import get_remote
from brain.routines.cli import routine_app

app = typer.Typer(help="Offline second brain CLI")
remote_app = typer.Typer(help="Manage sync remotes")
app.add_typer(remote_app, name="remote")
app.add_typer(routine_app, name="routine")


def _maybe_auto_backup() -> None:
    try:
        from brain.backup import BackupEngine
        from brain.config import BrainConfig

        cfg = BrainConfig.load_from()
        BackupEngine.maybe_trigger_backup(cfg)
    except Exception:
        pass


@app.command()
def init() -> None:
    run_init()


@app.command()
def add(
    path: str = typer.Argument(..., help="File or directory to ingest"),
) -> None:
    _maybe_auto_backup()
    run_add(path)


@app.command()
def ask(
    question: str = typer.Argument(..., help="Question to ask"),
    type: str | None = typer.Option(None, "--type", help="Filter by document type"),
    last: int | None = typer.Option(None, "--last", help="Last N days"),
    show_context: bool = typer.Option(
        False, "--show-context", help="Print retrieved context diagnostics"
    ),
) -> None:
    _maybe_auto_backup()
    run_ask(question, doc_type=type, last_ndays=last, show_context=show_context)


@app.command()
def status() -> None:
    _maybe_auto_backup()
    run_status()


@app.command()
def watch(
    path: str = typer.Argument(..., help="Directory to watch"),
) -> None:
    _maybe_auto_backup()
    run_watch(path)


@app.command()
def sync(
    remote_name: str = typer.Argument(..., help="Remote name (configured via 'brain remote add')"),
) -> None:
    try:
        remote = get_remote(remote_name)
    except KeyError:
        typer.echo(
            f"Error: remote '{remote_name}' not found. Use 'brain remote list' to see configured remotes.",
            err=True,
        )
        raise typer.Exit(1) from None
    _maybe_auto_backup()
    run_sync_s3(remote)


@remote_app.command("add")
def remote_add(
    name: str = typer.Argument(..., help="Remote name"),
    bucket: str = typer.Argument(..., help="Bucket name"),
    endpoint: str = typer.Argument(
        ..., help="S3-compatible endpoint URL (e.g. https://s3.amazonaws.com)"
    ),
    prefix: str = typer.Option("", "--prefix", help="Key prefix to sync"),
    key_id: str | None = typer.Option(None, "--key-id", help="Access key ID (stored in keyring)"),
    secret: str | None = typer.Option(
        None, "--secret", help="Secret access key (stored in keyring)"
    ),
) -> None:
    run_remote_add(name, bucket, prefix, endpoint, key_id, secret)


@remote_app.command("list")
def remote_list() -> None:
    run_remote_list()


@remote_app.command("remove")
def remote_remove(
    name: str = typer.Argument(..., help="Remote name to remove"),
) -> None:
    run_remote_remove(name)


@app.command(name="import")
def import_(
    path: str = typer.Argument(..., help="Raw text file to import"),
    title: str = typer.Option(..., "--title", help="Document title"),
    date: str = typer.Option(..., "--date", help="Document date (YYYY-MM-DD)"),
    type: str = typer.Option(..., "--type", help="Document type"),
    tags: list[str] | None = typer.Option(None, "--tag", help="Tags (repeatable)"),
    author: str | None = typer.Option(None, "--author", help="Author name"),
    structure: bool = typer.Option(
        False,
        "--structure",
        help="Use the local chat model to structure the raw transcript before ingesting",
    ),
) -> None:
    _maybe_auto_backup()
    run_import_raw(
        path,
        title=title,
        doc_date=date,
        doc_type=type,
        tags=tags or [],
        author=author,
        structure=structure,
    )


@app.command()
def chat() -> None:
    _maybe_auto_backup()
    run_chat()


@app.command()
def eval(
    path: str = typer.Argument(..., help="Directory of notes to evaluate"),
    run_ollama: bool = typer.Option(
        False, "--run-ollama", help="Actually call local Ollama models"
    ),
) -> None:
    try:
        run_eval(path, run_ollama=run_ollama)
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from None


@app.command()
def backup(
    list_flag: bool = typer.Option(False, "--list", help="List available backups"),
    restore: str | None = typer.Option(None, "--restore", help="Restore from a backup file"),
) -> None:
    run_backup(list_flag=list_flag, restore_path=restore)


@app.command()
def do(
    instruction: str = typer.Argument(
        ..., help="What to do, e.g. 'send yesterday meetings to slack'"
    ),
) -> None:
    run_do(instruction)


if __name__ == "__main__":
    app()
