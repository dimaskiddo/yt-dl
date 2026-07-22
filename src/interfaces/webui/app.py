"""Gradio WebUI orchestrator — builds UI and launches server."""

from __future__ import annotations

import gradio as gr

from src.core.config import get_config
from src.core.workspace import (
    cleanup_tmp,
    register_cleanup_hooks,
    run_purge_cycle,
    start_purge_scheduler,
)
from src.interfaces.webui.tabs.about import build_about_tab
from src.interfaces.webui.tabs.downloader import build_downloader_tab

# Trakteer overlay button JS injection
_TRAKTEER_LOAD_JS = """
() => {
  const slot = document.getElementById('trakteer-btn-slot');
  if (!slot || slot.dataset.done) return;
  slot.dataset.done = '1';

  const marker = document.createElement('script');
  marker.className = 'troverlay';
  slot.appendChild(marker);

  const lib = document.createElement('script');
  lib.src = 'https://edge-cdn.trakteer.id/js/trbtn-overlay.min.js?v=14-05-2025';
  lib.onload = () => {
    const id = trbtnOverlay.init(
      'Support This Project on Trakteer.ID', '#be1e2d',
      'https://trakteer.id/v1/itsdrh/tip/embed/modal',
      'https://edge-cdn.trakteer.id/images/embed/trbtn-icon.png?v=14-05-2025',
      '40', 'inline');
    trbtnOverlay.draw(id);
  };
  document.head.appendChild(lib);
}
"""


def build_ui() -> gr.Blocks:
    """Build the complete Gradio UI layout.

    Returns:
        Configured gr.Blocks instance.
    """
    cfg = get_config()

    with gr.Blocks(
        title="YouTube Downloader (YT-DL)", delete_cache=(1800, 3600)
    ) as app:
        gr.HTML(
            '<div style="display:flex;align-items:center;justify-content:space-between;'
            'margin-bottom:4px;">'
            '<h1 style="margin:0;font-size:1.75rem;">YouTube Downloader (YT-DL)</h1>'
            '<span id="trakteer-btn-slot" style="margin-left:auto;"></span>'
            "</div>"
        )

        build_downloader_tab(cfg)
        build_about_tab()

        # Inject trakteer overlay JS on page load
        app.load(None, js=_TRAKTEER_LOAD_JS)

    return app


def launch_webui(host: str | None = None, port: int | None = None) -> None:
    """Launch the Gradio WebUI server.

    Args:
        host: Host to bind to. Defaults to config value.
        port: Port to bind to. Defaults to config value.

    Returns:
        None — blocks until server is shut down.
    """
    config = get_config()
    bind_host = host or config.server.host
    bind_port = port or config.server.port

    # WebUI-specific startup (workspace init + binaries already done in app.py)
    cleanup_tmp()
    run_purge_cycle(config)
    register_cleanup_hooks()
    start_purge_scheduler(config)

    ui = build_ui()
    ui.queue().launch(
        server_name=bind_host,
        server_port=bind_port,
        show_error=False,
        allowed_paths=["workspace"],
    )
