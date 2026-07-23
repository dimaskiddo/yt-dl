FROM python:3.11-alpine

WORKDIR /usr/app

ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TZ=Asia/Jakarta

ENV PATH="/opt/venv/bin:$PATH" \
    VIRTUAL_ENV="/opt/venv"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HEADROOM_TELEMETRY=off

# Install system deps: FFmpeg for audio and video processing.
RUN apk upgrade --no-cache --update \
    && apk add --no-cache --update \
        ffmpeg

# Create non-root user.
RUN addgroup \
      -S \
      -g 1000 \
      user \
    && adduser \
        -S \
        -h /usr/app \
        -s /sbin/nologin \
        -u 1000 \
        -G user \
        user

# Copy only dependency manifest first (Docker layer caching).
COPY requirements.txt .

# Install packages into venv.
RUN PYTHON_MAIN_VERSION=`echo "${PYTHON_VERSION#*=}" | cut -d. -f1,2` \
    && python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip setuptools wheel \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt \
    && mkdir -p \
        /opt/venv/lib/python${PYTHON_MAIN_VERSION}/site-packages/static_ffmpeg/bin \
        /usr/app/.cache \
    && chown -R user:user \
        /opt/venv/lib/python${PYTHON_MAIN_VERSION}/site-packages/static_ffmpeg/bin \
        /usr/app/.cache \
    && chmod -R 777 \
        /opt/venv/lib/python${PYTHON_MAIN_VERSION}/site-packages/static_ffmpeg/bin \
        /usr/app/.cache

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
