"""Config command — show current configuration."""

from __future__ import annotations

import typer
import yaml

from src.core.config import load_config


def register(cli: typer.Typer) -> None:
    """Register config command with CLI app.

    Args:
        cli: Typer CLI application.
    """

    @cli.command("config")
    def show_config() -> None:
        """Show the current configuration."""
        cfg = load_config()
        data = cfg.model_dump()
        typer.echo(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
