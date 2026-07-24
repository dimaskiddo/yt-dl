# YT-DL — Workflows

Step-by-step data flow: YouTube URL → audio or video file.

---

## Pipeline Overview

```mermaid
flowchart TD
    Start([app.py]) --> Route{Args?}
    Route -- "None" --> WebUI[Gradio WebUI]
    Route -- "CLI" --> CLI[Typer Command]
    WebUI --> Boot
    CLI --> Boot

    subgraph S1["1. Boot"]
        Boot["init_workspace<br/>ensure_ffmpeg / ensure_bun<br/>setup_environment"]
    end

    S1 --> Download
    subgraph S2["2. Download"]
        Download["yt-dlp download<br/>→ workspace/tmp/{VIDEO_ID}/"]
    end

    Download --> Mode{Mode?}

    subgraph S3A["3a. Audio"]
        Mode -- "audio" --> Encode["FFmpeg re-encode<br/>bestaudio → target format/bitrate"]
    end

    subgraph S3B["3b. Video"]
        Mode -- "video" --> Merge["yt-dlp auto-merge<br/>bestvideo + bestaudio"]
        Merge --> Copy["FFmpeg stream copy"]
    end

    Encode --> Tag["3c. Inject ID3 (audio only)<br/>yt-dlp metadata → online search enrichment<br/>cover art (yt-dlp thumbnail / provider / default)<br/>mutagen ID3v2.4 / MP4 / VorbisComment"]
    Tag --> Move
    Copy --> Move

    subgraph S4["4. Cleanup"]
        Move["Move to final output<br/>workspace/audios/ or videos/"] --> Cleanup["Remove staging dir<br/>workspace/tmp/{VIDEO_ID}/"]
    end

    Cleanup --> Done([Complete])
```

---

## Stage Details

### 1. Boot (`src/core/workspace.py`)

- Create missing `workspace/` dirs via `init_workspace()`.
- Auto-download FFmpeg (via `static_ffmpeg` PyPI). Falls back to system PATH via `shutil.which()`.
- Auto-download Bun from GitHub releases (platform-specific zip). Auto-detects musl libc on Alpine — downloads `-musl` variant.
- Inject `workspace/bin` into PATH via `setup_environment()`.
- Register cleanup hooks (`atexit` + signal handlers) and hourly purge scheduler.

### 2. Download (`src/downloader/downloader.py`, `src/downloader/yt_dlp_config.py`)

- Extract video ID from URL via `extract_video_id()`.
- Build yt-dlp options via `build_ytdl_options()` — format selection, player client spoofing, bun JS runtime.
- Download with retry (exponential backoff, transient error classification).
- Source file lands in `workspace/tmp/{VIDEO_ID}/`.
- `ACTIVE_DOWNLOAD_EVENT` set during entire download+process cycle — blocks purge scheduler.

**Audio mode:** `bestaudio[ext=m4a]/bestaudio/best` — downloads audio stream only, no video. Fast.

**Video mode:** `bestvideo[ext=mp4][vcodec^=avc][height<=RES]+bestaudio[ext=m4a]/...` — downloads best video+audio, yt-dlp merges automatically via FFmpeg at `ffmpeg_location`.

### 3. Process (`src/downloader/downloader.py`, `src/downloader/ffmpeg_processor.py`)

**Audio:**
- FFmpeg re-encodes bestaudio to target format/bitrate.
- Codecs: MP3 (`libmp3lame`), AAC (`aac`), OPUS (`libopus`).
- Bitrates: 128K, 192K (default), 256K, 320K.

**Video:**
- yt-dlp merges video+audio. FFmpeg stream copies (zero quality loss, near-zero CPU).
- Resolutions: 360p, 480p, 720p (default), 1080p, 1440p.

**Output verification:**
- After FFmpeg completes, output file existence is verified on disk.
- `_finalize_output` raises `DownloadError` if processed output not found in staging — prevents silent retry loops.

### 4. Output & Cleanup

- Final output moved/copied from staging to `workspace/audios/` or `workspace/videos/`.
- Staging directory `workspace/tmp/{VIDEO_ID}/` removed.

---

## Audio Pipeline

```mermaid
flowchart TD
    URL([YouTube URL]) --> Extract["extract_video_id()"]
    Extract --> Ytdl["yt-dlp download<br/>format: bestaudio[ext=m4a]/bestaudio/best<br/>(fast — no video downloaded)"]
    Ytdl --> Staging["workspace/tmp/{VIDEO_ID}/source.{ext}"]
    Staging --> Encode["FFmpeg re-encode<br/>codec: libmp3lame / aac / libopus<br/>bitrate: 128K / 192K / 256K / 320K"]
    Encode --> Tag["inject_metadata()<br/>yt-dlp metadata → online search enrichment<br/>cover art (yt-dlp thumbnail / provider / default)<br/>mutagen ID3v2.4 / MP4 / VorbisComment"]
    Tag --> Output["workspace/audios/{VIDEO_ID}/{BITRATE}.{format}"]
    Output --> Cleanup["Remove staging dir"]
    Cleanup --> Done([Complete])
```

---

## Video Pipeline

```mermaid
flowchart TD
    URL([YouTube URL]) --> Extract["extract_video_id()"]
    Extract --> Ytdl["yt-dlp download<br/>format: bestvideo[ext=mp4][height<=RES]+bestaudio<br/>(yt-dlp merges automatically via FFmpeg)"]
    Ytdl --> Staging["workspace/tmp/{VIDEO_ID}/source.mp4"]
    Staging --> Copy["FFmpeg stream copy"]
    Copy --> Output["workspace/videos/{VIDEO_ID}/{RESOLUTION}.mp4"]
    Output --> Cleanup["Remove staging dir"]
    Cleanup --> Done([Complete])
```

---

## Staging Flow

All downloads use `workspace/tmp/{VIDEO_ID}/` as staging:

1. yt-dlp writes source to staging.
2. FFmpeg processes in staging (audio re-encode).
3. Final output moved/copied from staging to `workspace/audios/` or `workspace/videos/`.
4. Staging directory cleaned up.

---

## Cache Lifecycle

```mermaid
flowchart TD
    Startup(["Startup"]) --> CleanupTemp["cleanup_tmp()<br/>wipe workspace/tmp/"]
    CleanupTemp --> Hooks["register_cleanup_hooks()<br/>atexit + SIGINT/SIGTERM"]
    Hooks --> Scheduler["start_purge_scheduler()<br/>hourly daemon thread"]

    Scheduler --> Active["Downloads accumulate<br/>workspace/audios/ + videos/"]
    Active --> Purge{"Purge check<br/>(hourly)"}
    Purge -- "active download" --> Skip["Skip (ACTIVE_DOWNLOAD_EVENT)"]
    Skip --> Active
    Purge -- "no active download" --> Targets{"Purge targets"}
    Targets --> CheckAgeAud{"audios — Oldest file<br/>> retention days?"}
    Targets --> CheckAgeVid{"videos — Oldest file<br/>> retention days?"}
    Targets --> PurgeGradio["tmp/gradio/ — delete media files"]
    Targets --> PurgeServe["tmp/serve/ — delete media files"]
    CheckAgeAud -- "yes" --> DeleteAudio["Delete audio dir"]
    CheckAgeVid -- "yes" --> DeleteVideo["Delete video dir"]
    CheckAgeAud -- "no" --> Active
    CheckAgeVid -- "no" --> Active
    DeleteAudio --> Active
    DeleteVideo --> Active

    Shutdown(["Shutdown"]) --> FinalCleanup["atexit handler<br/>cleanup_tmp()"]
```

Retention: `audio_days` / `video_days` / `tmp_days` from `config.yaml` (`0` = immediate, `-1` = skip). Purge targets: `audios/` and `videos/` (by age), `tmp/gradio/` and `tmp/serve/` (by age). Staging dirs (`tmp/{VIDEO_ID}/`) are never purged. Protected dirs (never purged): `bin/`, `logs/`.

---

## Binary Lifecycle

```mermaid
flowchart TD
    Start([App startup]) --> CheckFFmpeg{"ffmpeg in<br/>workspace/bin/?"}
    CheckFFmpeg -- "yes, real file" --> CheckBun
    CheckFFmpeg -- "no" --> DLFFmpeg["Download via static_ffmpeg PyPI<br/>copy to workspace/bin/"]
    DLFFmpeg -- "success" --> CheckBun
    DLFFmpeg -- "fail" --> SystemPath["System PATH via shutil.which()"]
    SystemPath --> CheckBun

    CheckBun{"bun in<br/>workspace/bin/?"}
    CheckBun -- "yes, real file" --> PATH
    CheckBun -- "no" --> DetectMusl{"musl libc?<br/>(Alpine)"}
    DetectMusl -- "yes" --> DLBunMusl["Download bun-linux-*-musl.zip<br/>from GitHub releases"]
    DetectMusl -- "no" --> DLBun["Download bun-linux-*.zip<br/>from GitHub releases"]
    DLBunMusl --> PATH
    DLBun --> PATH

    PATH["Prepend workspace/bin/ to PATH<br/>via setup_environment()"]
    PATH --> Ready([Ready])
```

---

## CLI Workflow

```mermaid
flowchart TD
    Start([app.py]) --> LoadConfig["load_config()"]
    LoadConfig --> Args{"sys.argv > 1?"}
    Args -- "yes" --> Typer["Typer CLI"]

    subgraph Commands["Commands"]
        Download["download <URL> [-m mode] [-b bitrate] [-f format] [-r resolution] [--force]"]
        ConfigCmd["config"]
        Cache["cache status | purge | clean"]
        Serve["serve [--host] [--port]"]
    end

    Typer --> Commands
    Serve --> WebUI["launch_webui()"]
    Download --> Execute["VideoDownloader.download()"]
```

---

## WebUI Workflow

```mermaid
flowchart TD
    Start([app.py]) --> LoadConfig["load_config()"]
    LoadConfig --> Launch["launch_webui()"]
    Launch --> Boot["setup_environment()<br/>init_workspace()<br/>cleanup_tmp()<br/>register_cleanup_hooks()<br/>start_purge_scheduler()"]
    Boot --> BuildUI["build_ui()"]

    subgraph UI["Gradio UI"]
        Header["Header — title + trakteer overlay"]
        Tab1["Downloader tab<br/>URL input, mode radio<br/>audio: bitrate + format<br/>video: resolution"]
        Tab2["About tab"]
        Header --> Tab1
        Header --> Tab2
    end

    BuildUI --> UI
    Tab1 --> Download["Download button → asyncio.to_thread(VideoDownloader.download)"]
    Download --> Result["Status + file output"]
    UI --> Queue["ui.queue().launch()"]
```

---

## File Naming Conventions

| File | Location | Pattern |
|---|---|---|
| Audio output | `audios/` | `{VIDEO_ID_UPPERCASE}/{BITRATE}.{format}` |
| Video output | `videos/` | `{VIDEO_ID_UPPERCASE}/{RESOLUTION}.mp4` |
| Staging source | `tmp/` | `{VIDEO_ID}/source.{ext}` |
| App logs | `logs/` | `app.log` |
