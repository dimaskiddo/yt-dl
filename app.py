#!/usr/bin/env python3
"""YT-DL entry point — routes CLI args to Typer, bare invocation to Gradio."""

from __future__ import annotations

import sys

from src.core.config import get_config, load_config
from src.core.environment import setup_environment
from src.core.logger import setup_logger
from src.core.workspace import ensure_bun, ensure_ffmpeg, init_workspace


def main() -> None:
    """Entry point. Load config, init workspace, then route to CLI or WebUI."""
    try:
        load_config()
        setup_logger(get_config().logging)
    except Exception as e:
        print(f"Startup failed: {e}")
        sys.exit(1)

    # Shared startup — both CLI and WebUI need workspace + binaries
    config = get_config()
    setup_environment(config.workspace.bin)
    init_workspace(config)
    ensure_ffmpeg(config.workspace.bin)
    ensure_bun(config.workspace.bin)

    if len(sys.argv) > 1:
        from src.interfaces.cli import cli

        cli()
    else:
        from src.interfaces.webui import launch_webui

        launch_webui()


if __name__ == "__main__":
    main()
