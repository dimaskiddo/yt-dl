# YT-DL — Agent Instructions

Build a clean, robust, and low-spec optimized YouTube Downloader application. Dual Interfaces: CLI (`typer`) + WebUI (`gradio`) with Background Task Processing. Powered by Python, `yt-dlp`, `ffmpeg-static`, Bun (JS Engine for yt-dlp EJS), and `gradio`.

---

## Workflow Rules

1. Read `TASKS.md` before every session to orient to current state.
2. Never rework items marked `[x]` in `TASKS.md` unless explicitly instructed.
3. Update `TASKS.md` immediately after testing a feature.
4. Never attempt to write the entire codebase in a single response.
5. Create `TASKS.md`, `docs/ARCHITECTURE.md`, `docs/WORKFLOWS.md` during project init.

## Skills & Caveman Mode

- **GLOBAL:** All prompts processed as if `"Use caveman mode full"` is injected.
- Before ANY coding task, invoke and read: `using-superpowers`, `karpathy-guidelines`, `caveman`.
- Use `using-superpowers` to route to other relevant skills per task.

---

## Downloader Modes & File Hierarchy

### 1. Audio Mode
- **Best Quality Source:** Downloads best available audio stream only (no video — faster download).
- **Re-encoding:** After download, re-encodes to target bitrate/format via FFmpeg.
- **Bitrate Options:** `128K`, `192K`, `256K`, `320K` (Default: `192K`).
- **Format Options:** `MP3`, `AAC`, `OPUS` (Default: `MP3`).
- **Output Directory Structure:** `workspace/audios/{VIDEO_ID_UPPERCASE}/{QUALITY}.{format}`
  *Example:* `workspace/audios/AKS7Y8P/192K.aac`

### 2. Video Mode
- **Resolution Options:** `360p`, `480p`, `720p`, `1080p`, `1440p` (Default: `720p`).
- **Format Options:** `MP4` (Default).
- **Quality Strategy:** yt-dlp downloads best video+audio and merges automatically. FFmpeg stream copies (no re-encode, zero quality loss).
- **Output Directory Structure:** `workspace/videos/{VIDEO_ID_UPPERCASE}/{RESOLUTION_UPPERCASE}.{format}`
  *Example:* `workspace/videos/AKS7Y8P/1080P.mp4`

### 3. Staging Flow
- All downloads stage in `workspace/tmp/{VIDEO_ID}/` first.
- After processing, final output moves to `workspace/audios/` or `workspace/videos/`.
- Staging cleaned up after each download.

### 4. Execution & Progress
- Downloads run synchronously in background thread (via `asyncio.to_thread` in WebUI).
- UI/CLI displays real-time progress (Download % → FFmpeg Encoding/Merging % → Complete).

---

## Critical Constraints

### Python Ecosystem
- `.venv` mandatory. `source .venv/bin/activate` (Linux/macOS) or `.\.venv\Scripts\activate` (Windows) or `uv run`. Never touch global Python.
- Package install: `uv` preferred or `pip3`. Always `--no-cache-dir`/`--no-cache`.
- All runtime assets in `./workspace/`. Never `/tmp/` or `%TEMP%`.
- Startup boot: verify and auto-download binaries in `workspace/bin/` (FFmpeg, Bun).

### Interfaces
- **CLI:** `typer`. Commands: `download <URL>`, `config`, `cache status/purge/clean`, `serve`.
- **WebUI:** `gradio`. Tabs: Downloader, About. Always `.queue().launch()`.
- `app.py` = entry/router only. CLI args → Typer; bare → Gradio.
- Gradio binds `127.0.0.1:7860` (configurable).

### Configuration
- Single `config.yaml` in project root. Pydantic validated at startup (`src/core/config.py`). Full reference: `config.yaml.example`.
- First run: copies `config.yaml.example` → `config.yaml`.

### Cache & Purge
- Startup: `cleanup_tmp()` wipes `workspace/tmp/` (serve, Gradio, staging leftovers).
- Shutdown: `atexit` + signal handlers call `cleanup_tmp()`.
- Background scheduler: `run_purge_cycle()` runs hourly. Retention: `audio_days` / `video_days` / `tmp_days` (`0` = immediate, `-1` = skip). Protected: `bin/`, `logs/`.
- Guard: `ACTIVE_DOWNLOAD_EVENT` skips purge during active downloads.

### Binaries
- FFmpeg: downloaded via `static_ffmpeg` PyPI package to `workspace/bin/`.
- Bun: downloaded from GitHub releases (platform-specific zip) to `workspace/bin/`.
- Both prepend to `PATH` via `setup_environment()`.

---

## Python Standards

- **Constants (CRITICAL):** Before implementing any module, read `src/core/constants.py` for exact bitrates, resolutions, default formats, and path definitions. Never guess numeric constants — the file is the single source of truth.
- **Type hints:** Every function fully annotated. `X | None` (not Optional). `from __future__ import annotations`. TypedDict for dict shapes, Pydantic BaseModel for data, Protocol for interfaces.
- **Pydantic:** All config, download requests, results, API responses = BaseModel. No raw dict access outside `config.py`.
- **Lazy imports:** Heavy modules (`yt_dlp`) imported inside execution functions only.
- **Exceptions:** Custom hierarchy in `src/core/exceptions.py`: `YTDownloaderError` → `ConfigValidationError`, `DownloadError`, `FFmpegError`, `InvalidURLError`. No bare `except:`. Chain with `raise X from Y`.
- **Logging:** Loguru only. No `print()`. Human-readable messages only — no developer-centric debug output. Config from `config.yaml`.
- **Paths:** `pathlib.Path` only. No `os.path.join` or string concat.
- **Subprocess:** List form only. No `shell=True`. Capture stderr, set timeout, pass `str(path)`.
- **Function design:** Max 40 lines. One function = one thing. Guard clauses, max 3 nesting levels. No boolean flags changing core behavior.
- **Resources:** `with` blocks / `contextlib.contextmanager` for all open/close lifecycles.
- **Async:** `asyncio.to_thread()` for offloading blocking from Gradio handlers.
- **Toolchain:** `ruff`, `mypy --strict`. Configured in `pyproject.toml`.
- **Docstrings:** Google-style (`Args:`, `Returns:`, `Raises:`). Comments explain *why*, not *what*.
- **Naming:** modules `snake_case`, classes `PascalCase`, functions `verb_noun`, constants `SCREAMING_SNAKE`, private `_prefix`. Downloaded folders: `{VIDEO_ID_UPPERCASE}`.

---

## Non-Negotiable Rules

1. **No stubs.** Never use `# ... rest of the code`, bare `pass`, or `# TODO`. Every file must be complete, production-ready, fully typed.
2. **Never auto-run pipeline.** Provide exact commands to test (`python app.py download <url>` or `python app.py serve`) and wait for user feedback.
3. **No guessing** on FFmpeg commands, yt-dlp format strings, or Gradio callback architecture. Describe the ambiguity + options, await decision.
4. **Never use system temp dirs.** All files in `./workspace/`.

---

## Directory Tree

```
ytdl-web/
├── app.py                    # Entry: routes CLI or WebUI
├── config.yaml               # User config (gitignored, copy from .example)
├── config.yaml.example       # Distributable config template
├── TASKS.md                  # Task tracking backlog
├── requirements.txt          # pip deps
├── requirements-dev.txt      # dev deps (ruff, pytest)
├── pyproject.toml            # uv/pip deps + ruff/mypy config
├── public/
│   └── trakteer-logo.png     # Trakteer overlay image
├── docs/
│   ├── ARCHITECTURE.md       # Module map, data flow
│   └── WORKFLOWS.md          # Pipeline diagrams
├── src/
│   ├── core/                 # config, constants, exceptions, environment, logger, utils, workspace
│   ├── downloader/           # yt_dlp_config, downloader, ffmpeg_processor
│   ├── metadata/             # ydl, cover, tagger, utils + providers (spotify, itunes, musicbrainz, lastfm)
│   └── interfaces/
│       ├── cli/              # app.py + commands/{download,config,cache,serve}.py
│       └── webui/            # app.py + components.py + tabs/{downloader,about}.py
└── workspace/
    ├── bin/                  # FFmpeg, Bun (auto-downloaded)
    ├── audios/               # Processed audio files (retention: audio_days)
    ├── videos/               # Processed video files (retention: video_days)
    ├── tmp/                  # Staging + Gradio temp (cleaned on startup/shutdown)
    └── logs/                 # Rotating loguru logs
```

---

## References

| File | Purpose |
|---|---|
| `config.yaml.example` | Full annotated config reference |
| `docs/ARCHITECTURE.md` | Module map, data flow, workspace layout |
| `docs/WORKFLOWS.md` | Pipeline flow diagrams, operational sequences |
| `TASKS.md` | Current project state — read before every session |
| `pyproject.toml` | Dependencies and ruff/mypy configuration |
| `app.py` | Entry point — routes CLI or WebUI |
| `src/core/constants.py` | All enums (`AudioFormat`, `VideoFormat`) and path constants |
| `src/core/config.py` | Pydantic config, YAML validation, singleton pattern |
| `src/core/exceptions.py` | Custom error hierarchy (`YTDownloaderError` → domain errors) |
| `src/core/workspace.py` | Workspace management, purge scheduler, binary lifecycle |
| `src/downloader/downloader.py` | Download orchestrator with retry and FFmpeg dispatch |
| `src/downloader/yt_dlp_config.py` | yt-dlp options builder |
| `src/downloader/ffmpeg_processor.py` | FFmpeg subprocess wrapper |
| `src/interfaces/cli/` | Typer CLI entry point and command modules |
| `src/interfaces/webui/` | Gradio WebUI entry point and tab modules |
| `src/metadata/` | Metadata extraction, online search (Spotify, MusicBrainz, iTunes, Last.fm), cover art, ID3 tag injection |
