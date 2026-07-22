"""Runtime environment setup — PATH and GRADIO_TEMP_DIR configuration."""

from __future__ import annotations

import os
from pathlib import Path


def setup_environment(workspace_bin: Path) -> None:
    """Configure runtime environment for binary discovery.

    Args:
        workspace_bin: Path to workspace/bin/ containing ffmpeg, bun.
    """
    # Redirect Gradio temp files to workspace
    gradio_tmp = str(Path("workspace") / "tmp" / "gradio")
    os.environ["GRADIO_TEMP_DIR"] = gradio_tmp

    # Prepend workspace/bin/ to PATH so ffmpeg/bun are discoverable
    bin_str = str(workspace_bin)
    current_path = os.environ.get("PATH", "")
    if bin_str not in current_path:
        os.environ["PATH"] = f"{bin_str}{os.pathsep}{current_path}"
