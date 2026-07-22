"""CLI app setup and command registration."""

from __future__ import annotations

import typer

from src.interfaces.cli.commands import cache as cache_cmd
from src.interfaces.cli.commands import config as config_cmd
from src.interfaces.cli.commands import download as download_cmd
from src.interfaces.cli.commands import serve as serve_cmd

cli = typer.Typer(
    help="YT-DL — YouTube Downloader",
    add_completion=False,
)
cache_app = typer.Typer(help="Cache management commands")
cli.add_typer(cache_app, name="cache")

# Register commands
download_cmd.register(cli)
config_cmd.register(cli)
cache_cmd.register(cache_app)
serve_cmd.register(cli)

# Re-export for bare invocation
serve = serve_cmd.serve
