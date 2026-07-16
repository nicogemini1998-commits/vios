"""CLI `vios` — M0: --version, health."""
import httpx
import typer

from . import __version__
from .config import load_settings

app = typer.Typer(help="VIOS command line")


@app.command()
def health() -> None:
    """Golpea el engine y reporta estado. Exit 0 = ok, !=0 = engine caído/degradado."""
    settings = load_settings()
    url = f"http://localhost:{settings.engine_port}/health"
    try:
        resp = httpx.get(url, timeout=5)
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"engine unreachable: {exc}")
        raise typer.Exit(code=2) from exc
    typer.echo(data)
    raise typer.Exit(code=0 if data.get("status") == "ok" else 1)


def _version_cb(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", callback=_version_cb, is_eager=True
    ),
) -> None:
    """VIOS engine CLI."""
