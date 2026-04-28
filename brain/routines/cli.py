from __future__ import annotations

import typer

from brain.config import BrainConfig
from brain.routines.registry import list_actions
from brain.routines.runner import run_routine
from brain.routines.scheduler import RoutineDaemon

routine_app = typer.Typer(help="Manage routines")


@routine_app.command("list")
def routine_list() -> None:
    cfg = BrainConfig.load_from()
    actions = list_actions()

    if not cfg.routines:
        typer.echo("No routines configured.")
        typer.echo(f"Available actions: {', '.join(sorted(actions))}")
        return

    max_name = max(len(r.name) for r in cfg.routines)
    max_action = max(len(r.action) for r in cfg.routines)

    header = f"{'Name':<{max_name}}  {'Action':<{max_action}}  Trigger          Status"
    typer.echo(header)
    typer.echo("-" * len(header))

    for r in cfg.routines:
        trigger_str = r.trigger.value if r.trigger.value else r.trigger.type
        status = "enabled" if r.enabled else "disabled"
        if r.action not in actions:
            status += " (action missing)"
        typer.echo(f"{r.name:<{max_name}}  {r.action:<{max_action}}  {trigger_str:<16} {status}")

    available = set(actions.keys()) - {r.action for r in cfg.routines}
    if available:
        typer.echo(f"\nAvailable actions: {', '.join(sorted(available))}")


@routine_app.command("run")
def routine_run(
    name: str = typer.Argument(..., help="Routine name to run"),
) -> None:
    result = run_routine(name)
    if result.success:
        typer.echo(f"Routine '{name}' succeeded: {result.message}")
    else:
        typer.echo(f"Routine '{name}' failed: {result.message}", err=True)
        raise typer.Exit(1)


@routine_app.command("daemon")
def routine_daemon() -> None:
    daemon = RoutineDaemon()
    daemon.start()


@routine_app.command("enable")
def routine_enable(
    name: str = typer.Argument(..., help="Routine name to enable"),
) -> None:
    cfg = BrainConfig.load_from()
    for r in cfg.routines:
        if r.name == name:
            r.enabled = True
            cfg.save_to()
            typer.echo(f"Routine '{name}' enabled.")
            return
    typer.echo(f"Routine '{name}' not found.", err=True)
    raise typer.Exit(1)


@routine_app.command("disable")
def routine_disable(
    name: str = typer.Argument(..., help="Routine name to disable"),
) -> None:
    cfg = BrainConfig.load_from()
    for r in cfg.routines:
        if r.name == name:
            r.enabled = False
            cfg.save_to()
            typer.echo(f"Routine '{name}' disabled.")
            return
    typer.echo(f"Routine '{name}' not found.", err=True)
    raise typer.Exit(1)
