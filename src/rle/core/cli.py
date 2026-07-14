"""Command-line interface for rle-python core."""

import typer
from typing import Annotated

from rle.core import __version__

app = typer.Typer(
    name="rle",
    help="IUCN Red List of Ecosystems tools (core)",
    add_completion=False,
)


@app.command()
def backends():
    """List installed data-access backends (core + any plugins)."""
    from rle.core.registry import iter_backends

    infos = iter_backends()
    if not infos:
        print("No backends registered.")
        return
    width = max(len(b.name) for b in infos)
    for b in sorted(infos, key=lambda x: (x.capability, x.name)):
        dist = f"  [{b.distribution}]" if b.distribution else ""
        print(f"  {b.name:<{width}}  {b.capability}{dist}")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option("--version", "-v", help="Show version and exit"),
    ] = False,
):
    """Main entry point for the rle CLI."""
    if version:
        print(f"rle-python version {__version__}")
        raise typer.Exit()

    if ctx.invoked_subcommand is None:
        print("Hello from rle-python!")
        print("\nUse --help to see available commands")


if __name__ == "__main__":
    app()
