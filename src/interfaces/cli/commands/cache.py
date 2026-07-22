"""Cache commands — status, purge, clean."""

from __future__ import annotations

from pathlib import Path

import typer
from loguru import logger

from src.core.config import get_config, load_config
from src.core.constants import WORKSPACE_ROOT, WORKSPACE_TMP
from src.core.logger import setup_logger
from src.core.workspace import cache_usage, clean_dir, run_purge_cycle

_CLEAN_TARGETS: dict[str, Path] = {
    "audios": WORKSPACE_ROOT / "audios",
    "videos": WORKSPACE_ROOT / "videos",
    "tmp": WORKSPACE_TMP,
    "logs": WORKSPACE_ROOT / "logs",
}

_DIR_LABELS: dict[str, str] = {
    "audios": "Audios",
    "videos": "Videos",
    "tmp": "Temp",
    "logs": "Logs",
}

_DIR_ORDER: dict[str, int] = {
    "audios": 0,
    "videos": 1,
    "tmp": 2,
    "logs": 3,
}


def _format_oldest(days: float | None) -> str:
    """Format oldest file age for display.

    Args:
        days: Age in days, or None if no files exist.

    Returns:
        Formatted string like "3.2d" or "-".
    """
    return f"{days:.1f}d" if days is not None else "-"


def _print_cache_table() -> None:
    """Print per-directory cache status table."""
    rows = sorted(cache_usage(), key=lambda r: _DIR_ORDER.get(r["name"], 99))  # type: ignore[arg-type]

    typer.echo(f"{'dir':<12}{'size (MB)':>12}{'files':>8}{'oldest':>12}")
    for row in rows:
        label = _DIR_LABELS.get(row["name"], row["name"].title())  # type: ignore[arg-type]
        typer.echo(
            f"{label:<12}{row['size_mb']:>12.1f}{row['count']:>8}{_format_oldest(row['oldest_days']):>12}"
        )


def _validate_clean_targets(target: list[str] | None) -> list[str]:
    """Validate and resolve clean targets.

    Args:
        target: Requested targets, or None for all.

    Returns:
        Sorted list of valid target names.

    Raises:
        typer.Exit: If unknown targets specified.
    """
    valid = set(_CLEAN_TARGETS.keys())
    if target is None:
        return sorted(valid)

    unknown = [t for t in target if t not in valid]
    if unknown:
        typer.echo(f"Unknown targets: {', '.join(unknown)}")
        typer.echo(f"Valid: {', '.join(sorted(valid))}")
        raise typer.Exit(1)

    return sorted(target)


def register(cache_app: typer.Typer) -> None:
    """Register cache sub-commands.

    Args:
        cache_app: Typer app for cache sub-commands.
    """

    @cache_app.command("status")
    def cache_status() -> None:
        """Show per-directory size, file count, and oldest file in the workspace cache."""
        _print_cache_table()

    @cache_app.command("purge")
    def cache_purge() -> None:
        """Purge expired downloads based on retention policy."""
        config = load_config()
        run_purge_cycle(config)

    @cache_app.command("clean")
    def cache_clean(
        target: list[str] | None = typer.Argument(
            None,
            help="Directories to clean (audios videos tmp logs); all if omitted",
        ),
    ) -> None:
        """Clean workspace directories. Deletes all contents (keeps directory structure)."""
        _ = load_config()
        config = get_config()
        setup_logger(config.logging)

        target_sorted = _validate_clean_targets(target)
        logger.info("Cache clean: {}...", ", ".join(target_sorted))
        for t in target_sorted:
            clean_dir(_CLEAN_TARGETS[t])
