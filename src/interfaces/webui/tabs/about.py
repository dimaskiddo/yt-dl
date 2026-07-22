"""About tab — static project information."""

from __future__ import annotations

from types import SimpleNamespace

import gradio as gr


def build_about_tab() -> SimpleNamespace:
    """Build the About tab UI.

    Returns:
        SimpleNamespace with tab attribute.
    """
    with gr.Tab("About") as about_tab:
        gr.Markdown(
            "## What's YT-DL?\n\n"
            "**YouTube ➜ Audio or Video — in one click.**\n\n"
            "YT-DL is a clean, lightweight YouTube downloader that wrap "
            "yt-dlp. Download any public YouTube video as "
            "audio (MP3/AAC/OPUS) or video (MP4) at your preferred quality.\n\n"
            "---\n\n"
            "### ✦ Quick Links\n\n"
            "- **\U0001f3e0 Homepage** → [dimaskiddo.my.id](https://dimaskiddo.my.id)\n"
            "- **☕ Support Me** → [gift.trakteer.id/itsdrh](https://gift.trakteer.id/itsdrh)\n\n"
            "---\n\n"
            "### ⚡ Powered By\n\n"
            "**[Trakteer.ID](https://trakteer.id)** — *Where Creator and Supporter Met Together "
            "in One Place!*"
        )
        gr.Image(
            value="public/trakteer-logo.png",
            show_label=False,
            container=False,
            interactive=False,
            buttons=[],
            height=28,
            width=136,
        )

    return SimpleNamespace(tab=about_tab)
