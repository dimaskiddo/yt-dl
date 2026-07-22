"""Downloader tab — main download interface."""

from __future__ import annotations

import asyncio
import secrets
from types import SimpleNamespace

import gradio as gr

from src.core.config import AppConfig, get_config
from src.core.constants import GRADIO_TEMP_DIR, WORKSPACE_TMP
from src.core.utils import format_bytes, sanitize_filename, validate_youtube_url
from src.downloader.downloader import DownloadRequest, VideoDownloader
from src.interfaces.webui.components import (
    AUDIO_BITRATE_CHOICES,
    AUDIO_FORMAT_CHOICES,
    MODE_CHOICES,
    VIDEO_RESOLUTION_CHOICES,
)


def _generate_session_id() -> str:
    """Generate a 6-char uppercase hex session ID.

    Returns:
        6-character uppercase hex string.
    """
    return secrets.token_hex(3).upper()


def _generate_serve_name(
    result: object, title: str, mode: str, quality: str
) -> tuple[str, str]:
    """Build unique serve filename with mode/quality prefix and random ID.

    Args:
        result: DownloadResult with output_path and video_id.
        title: Sanitized video title (empty string if unavailable).
        mode: Download mode (``audio`` or ``video``).
        quality: Bitrate (e.g. ``192K``) for audio, resolution (e.g. ``1080p``) for video.

    Returns:
        Tuple of ``(session_id, filename)`` where filename has format
        ``{RAND6}_{AUD|VID}-{QUALITY}_{title}{ext}``.
    """
    random_id = _generate_session_id()
    mode_prefix = "AUD" if mode == "audio" else "VID"
    quality_tag = quality.upper()
    tag = f"{mode_prefix}-{quality_tag}"
    ext = result.output_path.suffix
    label = title if title else result.video_id.upper()
    return random_id, f"{random_id}_{tag}_{label}{ext}"


def _create_serve_path(
    result: object,
    title: str,
    mode: str,
    quality: str,
) -> tuple[str, str]:
    """Create hardlink for Gradio preview and return absolute path + session ID.

    Args:
        result: DownloadResult with output_path and video_id.
        title: Sanitized video title for filename.
        mode: Download mode (``audio`` or ``video``).
        quality: Bitrate for audio or resolution for video.

    Returns:
        Tuple of ``(absolute_path_to_served_file, session_id)``.
    """
    serve_dir = WORKSPACE_TMP / "serve"
    serve_dir.mkdir(parents=True, exist_ok=True)

    session_id, serve_name = _generate_serve_name(result, title, mode, quality)
    serve_path = serve_dir / serve_name
    try:
        serve_path.unlink(missing_ok=True)
        serve_path.hardlink_to(result.output_path)
        return str(serve_path.resolve()), session_id
    except OSError:
        pass

    return str(result.output_path.resolve()), session_id


def _clean_session_files(session_id: str) -> None:
    """Delete files belonging to a download session from serve and Gradio cache.

    Removes hardlinks from ``workspace/tmp/serve/{session_id}_*`` and
    scans ``workspace/tmp/gradio/`` subdirs for files containing the session ID.

    Args:
        session_id: 6-char uppercase hex session identifier.
    """
    # Clean serve directory
    serve_dir = WORKSPACE_TMP / "serve"
    if serve_dir.exists():
        total = 0
        freed = 0.0
        for f in serve_dir.iterdir():
            if f.is_file() and f.name.startswith(session_id):
                total += 1
                freed += f.stat().st_size / (1024 * 1024)
                f.unlink(missing_ok=True)

    # Clean Gradio temp directory
    gradio_dir = GRADIO_TEMP_DIR
    if gradio_dir.exists():
        for subdir in list(gradio_dir.iterdir()):
            if subdir.is_dir():
                for f in list(subdir.iterdir()):
                    if f.is_file() and session_id in f.name:
                        total += 1
                        freed += f.stat().st_size / (1024 * 1024)
                        f.unlink(missing_ok=True)
                # Remove empty hash dir after session files deleted
                if not any(subdir.iterdir()):
                    subdir.rmdir()

    if total > 0:
        from loguru import logger

        logger.info("Cleaned {} session file(s) ({:.2f} MB)", total, freed)


def _build_success_updates(preview_path: str, mode: str, session_id: str) -> tuple:
    """Build UI updates for successful download.

    Args:
        preview_path: Path to preview file.
        mode: Download mode (audio or video).
        session_id: Session ID for cleanup tracking.

    Returns:
        Tuple of 10 gr.update values.
    """
    is_audio = mode == "audio"
    # CSS classes on preview_panel hide the inactive media component.
    # Gradio's visible=False on gr.Audio/gr.Video is unreliable when parent
    # Column transitions visible=False → True in the same update batch.
    hide_class = "hide-video" if is_audio else "hide-audio"
    return (
        gr.update(visible=False),  # download_btn
        gr.update(interactive=True),  # url_input
        gr.update(visible=False),  # quality_panel
        gr.update(value=preview_path if is_audio else None),  # preview_audio
        gr.update(value=None if is_audio else preview_path),  # preview_video
        gr.update(visible=True, elem_classes=[hide_class]),  # preview_panel
        gr.update(visible=False),  # error_box
        gr.update(visible=True),  # new_download_btn
        gr.update(interactive=True),  # force_checkbox
        gr.update(value=session_id),  # session_input
    )


def _build_error_updates(error: Exception) -> tuple:
    """Build UI updates for failed download.

    Args:
        error: The exception that occurred.

    Returns:
        Tuple of 10 gr.update values.
    """
    return (
        gr.update(
            interactive=True, value="Download", variant="primary"
        ),  # download_btn
        gr.update(interactive=True),  # url_input
        gr.update(visible=True),  # quality_panel
        gr.update(value=None),  # preview_audio
        gr.update(value=None),  # preview_video
        gr.update(visible=False, elem_classes=[]),  # preview_panel
        gr.update(visible=False),  # error_box (kept hidden — errors shown via gr.Warning toast)
        gr.update(visible=False),  # new_download_btn
        gr.update(interactive=True),  # force_checkbox
        gr.update(value=""),  # session_input
    )


async def _download_video(
    url: str,
    mode: str,
    audio_bitrate: str,
    audio_format: str,
    video_resolution: str,
    force: bool = False,
    progress: gr.Progress = gr.Progress(),
) -> tuple:
    """Execute download with progress feedback.

    Args:
        url: YouTube URL.
        mode: "audio" or "video".
        audio_bitrate: Target bitrate.
        audio_format: Target audio format.
        video_resolution: Target video resolution.
        force: Re-download even if cached.
        progress: Gradio progress reporter.

    Returns:
        Tuple of 8 updates for UI components.
    """
    cfg = get_config()

    try:
        url = validate_youtube_url(url)

        progress(0.2, desc="Preparing...")
        request = DownloadRequest(
            url=url,
            mode=mode,
            audio_bitrate=audio_bitrate,
            audio_format=audio_format,
            video_resolution=video_resolution,
            video_format=cfg.downloader.video_format,
        )

        downloader = VideoDownloader(cfg)
        progress(0.6, desc="Downloading...")
        result = await asyncio.to_thread(downloader.download, request, force=force)

        size = format_bytes(
            result.output_path.stat().st_size if result.output_path.exists() else 0
        )
        title = (
            sanitize_filename(result.video_title)
            if result.video_title
            else result.video_id
        )
        progress(1.0, desc=f"Done — {title} ({size})")
        gr.Success("Download Complete", duration=5)

        preview_path, session_id = _create_serve_path(
            result,
            title,
            mode=mode,
            quality=audio_bitrate if mode == "audio" else video_resolution,
        )
        return _build_success_updates(preview_path, mode, session_id)
    except Exception as e:
        gr.Warning(str(e), duration=8)
        return _build_error_updates(e)


def _reset_form(session_id: str = "") -> tuple:
    """Reset form to initial state after download complete, cleaning session files.

    Args:
        session_id: Session ID for cleanup tracking. If non-empty, files matching
            this ID in serve and Gradio cache dirs are deleted.

    Returns:
        Tuple of 10 updates: (url_input, quality_panel, preview_audio, preview_video,
        preview_panel, error_box, download_btn, new_download_btn, force_checkbox, session_input).
    """
    if session_id:
        _clean_session_files(session_id)

    return (
        gr.update(
            visible=True, interactive=False, value="Download", variant="primary"
        ),  # download_btn
        gr.update(value="", interactive=True),  # url_input
        gr.update(visible=True),  # quality_panel
        gr.update(value=None),  # preview_audio
        gr.update(value=None),  # preview_video
        gr.update(visible=False, elem_classes=[]),  # preview_panel
        gr.update(visible=False),  # error_box
        gr.update(visible=False),  # new_download_btn
        gr.update(value=False, interactive=True),  # force_checkbox
        gr.update(value=""),  # session_input
    )


def _wire_events(
    mode_radio: gr.Radio,
    download_btn: gr.Button,
    url_input: gr.Textbox,
    quality_panel: gr.Column,
    preview_audio: gr.Audio,
    preview_video: gr.Video,
    preview_panel: gr.Column,
    error_box: gr.Textbox,
    new_download_btn: gr.Button,
    force_checkbox: gr.Checkbox,
    audio_bitrate: gr.Dropdown,
    audio_format: gr.Dropdown,
    video_resolution: gr.Dropdown,
    progress_bar: gr.Markdown,
    session_input: gr.Textbox,
) -> None:
    """Wire up event handlers for the Downloader tab.

    Args:
        mode_radio: Mode selection radio.
        download_btn: Download button.
        url_input: URL text input.
        quality_panel: Quality controls container.
        preview_audio: Audio preview component.
        preview_video: Video preview component.
        preview_panel: Preview container.
        error_box: Error display textbox.
        new_download_btn: New Download button.
        force_checkbox: Force Download checkbox.
        audio_bitrate: Audio bitrate dropdown.
        audio_format: Audio format dropdown.
        video_resolution: Video resolution dropdown.
        progress_bar: Progress display markdown.
        session_input: Hidden session ID textbox.
    """
    # Client-side Download button disable when URL empty
    url_input.change(
        fn=lambda url: gr.update(interactive=bool(url.strip())),
        inputs=[url_input],
        outputs=[download_btn],
        api_name=False,
    )

    # Client-side CSS toggle, no server round-trip
    mode_radio.change(
        None,
        inputs=[mode_radio],
        js="""
        (mode) => {
            document.querySelector('.audio-controls').classList.toggle('mode-hide', mode !== 'audio');
            document.querySelector('.video-controls').classList.toggle('mode-hide', mode !== 'video');
        }
        """,
        queue=False,
        api_name=False,
    )

    _ALL_OUTPUTS = [
        download_btn,
        url_input,
        quality_panel,
        preview_audio,
        preview_video,
        preview_panel,
        error_box,
        new_download_btn,
        force_checkbox,
        session_input,
    ]

    # Download: Phase 1 — instant UI lock, Phase 2 — download + post-download updates
    download_btn.click(
        fn=lambda: (
            gr.update(interactive=False, value="Downloading..."),
            gr.update(interactive=False),
            gr.update(visible=False),
            gr.update(),
            gr.update(),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(interactive=False),
            gr.update(),
        ),
        outputs=_ALL_OUTPUTS,
        queue=False,
        api_name=False,
    ).then(
        fn=_download_video,
        inputs=[
            url_input,
            mode_radio,
            audio_bitrate,
            audio_format,
            video_resolution,
            force_checkbox,
        ],
        outputs=_ALL_OUTPUTS,
        show_progress_on=[download_btn, progress_bar],
        api_name="download",
    )

    # New Download — reset form, clear previews, show quality panel
    new_download_btn.click(
        fn=_reset_form,
        inputs=[session_input],
        outputs=_ALL_OUTPUTS,
        api_name="new-download",
    )


def build_downloader_tab(cfg: AppConfig) -> SimpleNamespace:
    """Build the Downloader tab UI.

    Args:
        cfg: Application config for default values.

    Returns:
        SimpleNamespace with tab and component references.
    """
    with gr.Tab("Downloader") as tab:
        gr.HTML(
            "<style>"
            ".mode-hide{display:none!important}"
            "#mode-css-wrap{display:none!important}"
            "#download-progress{min-height:60px}"
            ".hide-audio #preview-audio{display:none!important}"
            ".hide-video #preview-video{display:none!important}"
            "</style>",
            head=(
                "<script>"
                "(function(){"
                "function h(r){r.querySelectorAll('*').forEach(function(e){"
                "if(e.shadowRoot){var s=e.shadowRoot.querySelector('.scroll');"
                "if(s)s.classList.add('noScrollbar');h(e.shadowRoot)}})}"
                "h(document);"
                "new MutationObserver(function(){h(document)})"
                ".observe(document.body,{childList:true,subtree:true});"
                "})();"
                "</script>"
            ),
            elem_id="mode-css-wrap",
        )

        url_input = gr.Textbox(
            label="YouTube URL",
            placeholder="https://youtube.com/watch?v=...",
        )

        force_checkbox = gr.Checkbox(label="Force Download", value=False)

        quality_panel = gr.Column(visible=True)
        with quality_panel:
            mode_radio = gr.Radio(
                choices=MODE_CHOICES,
                value=cfg.downloader.mode,
                label="Download Type",
            )
            is_audio = cfg.downloader.mode == "audio"

            with gr.Row():
                with gr.Column(
                    elem_classes=(
                        ["audio-controls"]
                        if is_audio
                        else ["audio-controls", "mode-hide"]
                    )
                ):
                    audio_bitrate = gr.Dropdown(
                        choices=AUDIO_BITRATE_CHOICES,
                        value=cfg.downloader.audio_bitrate,
                        label="Bitrate",
                    )
                    audio_format = gr.Dropdown(
                        choices=AUDIO_FORMAT_CHOICES,
                        value=cfg.downloader.audio_format,
                        label="Format",
                    )
                with gr.Column(
                    elem_classes=(
                        ["video-controls", "mode-hide"]
                        if is_audio
                        else ["video-controls"]
                    )
                ):
                    video_resolution = gr.Dropdown(
                        choices=VIDEO_RESOLUTION_CHOICES,
                        value=cfg.downloader.video_resolution,
                        label="Resolution",
                    )

        preview_panel = gr.Column(visible=False)
        with preview_panel:
            preview_audio = gr.Audio(
                visible=True,
                interactive=False,
                label="Preview",
                buttons=["download"],
                elem_id="preview-audio",
            )
            preview_video = gr.Video(
                visible=True,
                interactive=False,
                label="Preview",
                height=360,
                buttons=["download"],
                elem_id="preview-video",
            )

        error_box = gr.Textbox(label="Status", interactive=False, visible=False)
        download_btn = gr.Button("Download", variant="primary", interactive=False)
        new_download_btn = gr.Button("New Download", variant="secondary", visible=False)
        progress_bar = gr.Markdown("", elem_id="download-progress")
        session_input = gr.Textbox(visible=False)

        # Generate fresh session ID on every page load / tab switch
        tab.select(
            fn=lambda: gr.update(value=_generate_session_id()),
            outputs=[session_input],
            api_name=False,
            queue=False,
        )

        _wire_events(
            mode_radio,
            download_btn,
            url_input,
            quality_panel,
            preview_audio,
            preview_video,
            preview_panel,
            error_box,
            new_download_btn,
            force_checkbox,
            audio_bitrate,
            audio_format,
            video_resolution,
            progress_bar,
            session_input,
        )

    return SimpleNamespace(
        tab=tab,
        url_input=url_input,
        mode_radio=mode_radio,
        download_btn=download_btn,
        new_download_btn=new_download_btn,
        session_input=session_input,
    )
