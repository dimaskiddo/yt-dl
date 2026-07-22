"""Serve command — launch Gradio WebUI."""

from __future__ import annotations

import typer

from src.core.config import get_config


def serve(
    host: str | None = typer.Option(
        None, "--host", "-h", help="Host to bind to (default: from config)"
    ),
    port: int | None = typer.Option(
        None, "--port", "-p", help="Port to bind to (default: from config)"
    ),
) -> None:
    """Launch the YouTube Downloader WebUI for downloading YouTube audios or videos.

    Args:
        host: Host to bind to. Defaults to config value.
        port: Port to bind to. Defaults to config value.
    """
    config = get_config()
    bind_host = host or config.server.host
    bind_port = port or config.server.port

    _launch_webui(bind_host, bind_port)


def _launch_webui(host: str | None = None, port: int | None = None) -> None:
    """Launch WebUI directly without Typer (bare invocation path).

    Args:
        host: Host to bind to. Defaults to config value.
        port: Port to bind to. Defaults to config value.
    """
    from src.interfaces.webui import launch_webui

    launch_webui(host, port)


def register(cli: typer.Typer) -> None:
    """Register serve command with CLI app.

    Args:
        cli: Typer CLI application.
    """
    cli.command("serve")(serve)
