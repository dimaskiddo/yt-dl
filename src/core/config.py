"""Pydantic configuration models and YAML loader with singleton pattern."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

from src.core.constants import (
    AUDIO_FORMAT_DEFAULT,
    BITRATE_DEFAULT,
    BITRATE_OPTIONS,
    DEFAULT_HOST,
    DEFAULT_PORT,
    RESOLUTION_DEFAULT,
    RESOLUTION_OPTIONS,
    VIDEO_FORMAT_DEFAULT,
)
from src.core.exceptions import ConfigValidationError


class DownloaderConfig(BaseModel):
    """Downloader settings for audio/video modes."""

    mode: str = Field(default="audio")
    audio_format: str = Field(default=AUDIO_FORMAT_DEFAULT.value)
    audio_bitrate: str = Field(default=BITRATE_DEFAULT)
    video_resolution: str = Field(default=RESOLUTION_DEFAULT)
    video_format: str = Field(default=VIDEO_FORMAT_DEFAULT.value)
    max_attempts: int = Field(default=3, ge=1, le=10)
    retry_delay: float = Field(default=2.0, ge=0.5, le=60.0)

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        if v not in ("audio", "video"):
            raise ValueError(f"mode must be 'audio' or 'video', got '{v}'")
        return v

    @field_validator("audio_format")
    @classmethod
    def validate_audio_format(cls, v: str) -> str:
        from src.core.constants import AudioFormat

        valid = [f.value for f in AudioFormat]
        if v not in valid:
            raise ValueError(f"audio_format must be one of {valid}, got '{v}'")
        return v

    @field_validator("audio_bitrate")
    @classmethod
    def validate_audio_bitrate(cls, v: str) -> str:
        if v not in BITRATE_OPTIONS:
            raise ValueError(
                f"audio_bitrate must be one of {BITRATE_OPTIONS}, got '{v}'"
            )
        return v

    @field_validator("video_resolution")
    @classmethod
    def validate_video_resolution(cls, v: str) -> str:
        if v not in RESOLUTION_OPTIONS:
            raise ValueError(
                f"video_resolution must be one of {RESOLUTION_OPTIONS}, got '{v}'"
            )
        return v

    @field_validator("video_format")
    @classmethod
    def validate_video_format(cls, v: str) -> str:
        if v not in ("mp4",):
            raise ValueError(f"video_format must be 'mp4', got '{v}'")
        return v


class WorkspaceConfig(BaseModel):
    """Workspace directory paths derived from root."""

    root: str = Field(default="workspace")

    @property
    def root_path(self) -> Path:
        return Path(self.root)

    @property
    def bin(self) -> Path:
        return Path(self.root) / "bin"

    @property
    def audios(self) -> Path:
        return Path(self.root) / "audios"

    @property
    def videos(self) -> Path:
        return Path(self.root) / "videos"

    @property
    def tmp(self) -> Path:
        return Path(self.root) / "tmp"

    @property
    def logs(self) -> Path:
        return Path(self.root) / "logs"


class CleanerSchedulerConfig(BaseModel):
    """Background purge scheduler settings."""

    enabled: bool = Field(default=True)
    interval_hours: int = Field(default=1, ge=1, le=168)

    @field_validator("interval_hours")
    @classmethod
    def validate_interval(cls, v: int) -> int:
        if v < 1 or v > 168:
            raise ValueError(f"interval_hours must be 1-168, got {v}")
        return v


class CleanerRetentionConfig(BaseModel):
    """Per-directory cache retention. 0 = immediate, -1 = never purge."""

    audio_days: int = Field(default=7)
    video_days: int = Field(default=7)
    tmp_days: int = Field(default=1)

    @field_validator("audio_days", "video_days", "tmp_days")
    @classmethod
    def validate_days(cls, v: int) -> int:
        if v < -1:
            raise ValueError(f"retention must be -1, 0, or positive, got {v}")
        return v


class CleanerConfig(BaseModel):
    """Workspace cleaner — retention + background scheduler."""

    scheduler: CleanerSchedulerConfig = Field(default_factory=CleanerSchedulerConfig)
    retention: CleanerRetentionConfig = Field(default_factory=CleanerRetentionConfig)


class ServerConfig(BaseModel):
    """Gradio WebUI server settings."""

    host: str = Field(default=DEFAULT_HOST)
    port: int = Field(default=DEFAULT_PORT)

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        if not (1 <= v <= 65535):
            raise ValueError(f"port must be 1-65535, got {v}")
        return v


class LoggingConfig(BaseModel):
    """Logging configuration for loguru."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    log_file: str = Field(default="app.log")
    rotation: str = Field(default="10 MB")
    retention: str = Field(default="7 days")


class AppConfig(BaseModel):
    """Root application configuration."""

    downloader: DownloaderConfig = Field(default_factory=DownloaderConfig)
    workspace: WorkspaceConfig = Field(default_factory=WorkspaceConfig)
    cleaner: CleanerConfig = Field(default_factory=CleanerConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


# Module-level singleton
_config: AppConfig | None = None


def load_config(path: Path = Path("config.yaml")) -> AppConfig:
    """Load config from YAML file, validate, and cache as singleton.

    If config.yaml doesn't exist, copies from config.yaml.example first.

    Args:
        path: Path to the config YAML file.

    Returns:
        Validated AppConfig instance.

    Raises:
        ConfigValidationError: If YAML content fails Pydantic validation.
    """
    global _config

    if not path.exists():
        example_path = path.parent / "config.yaml.example"
        if example_path.exists():
            shutil.copy2(example_path, path)
        else:
            raise ConfigValidationError(
                f"Neither {path} nor config.yaml.example found. Cannot initialize config."
            )

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise ConfigValidationError(f"Failed to parse {path}: {e}") from e

    try:
        _config = AppConfig.model_validate(raw)
    except ValidationError as e:
        raise ConfigValidationError(f"Invalid config in {path}: {e}") from e

    return _config


def get_config() -> AppConfig:
    """Return the cached config singleton.

    Raises:
        ConfigValidationError: If load_config() hasn't been called yet.
    """
    if _config is None:
        raise ConfigValidationError("Config not loaded. Call load_config() first.")
    return _config
