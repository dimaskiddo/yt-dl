FROM python:3.11-slim-bookworm

WORKDIR /usr/app

ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TZ=Asia/Jakarta \
    DEBIAN_FRONTEND=noninteractive

ENV PATH="/opt/venv/bin:$PATH" \
    VIRTUAL_ENV="/opt/venv"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HEADROOM_TELEMETRY=off

# Install system deps: FFmpeg for audio and video processing.
RUN apt-get -y update --allow-releaseinfo-change \
    && apt-get -y dist-upgrade \
    && apt-get -y install --no-install-recommends \
        ffmpeg \
    && apt-get -y purge --autoremove \
    && apt-get -y clean \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user.
RUN groupadd \
      --gid 1000 \
      user \
    && useradd \
        --no-create-home \
        --uid 1000 \
        --gid 1000 \
        -d /usr/app \
        -s /usr/sbin/nologin \
        user

# Copy only dependency manifest first (Docker layer caching).
COPY requirements.txt .

# Install packages into venv.
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip setuptools wheel \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

RUN /opt/venv/bin/python3 -c "\
import os; \
import static_ffmpeg; \
d = os.path.join(os.path.dirname(static_ffmpeg.__file__), 'bin', 'linux'); \
os.makedirs(d, mode=0o777, exist_ok=True);"

# Copy the rest of the application.
COPY . .

# Persistent workspace: audios, videos, bin, logs survive container restarts.
VOLUME /usr/app/workspace

# Expose Gradio WebUI port.
EXPOSE 7860

# Set user as non-root user.
USER user

# Default: serve the WebUI (override via CLI args: `download <url>`, `cache purge`, etc.).
# The workspace auto-initialises on first boot (FFmpeg, dirs).
ENTRYPOINT ["python3", "app.py"]
CMD ["serve"]
