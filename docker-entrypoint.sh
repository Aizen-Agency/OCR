#!/bin/bash
set -e

# Note: PaddlePaddle cache directories are configured in Python code (ROOT CAUSE FIX)
# No more global HOME manipulation - using explicit PaddlePaddle environment variables

# Setup directories for PaddleX cache (mounted at /tmp/.paddlex)
if [ "$(id -u)" = "0" ]; then
    # Create PaddleX cache directories (volume is mounted at /tmp/.paddlex)
    # PaddlePaddle environment variables configure cache location (not HOME manipulation)
    mkdir -p /tmp/.paddlex/temp
    mkdir -p /tmp/.paddlex/official_models

    # Fix ownership on the volume (volumes are writable even with read_only: true)
    chown -R ocruser:ocruser /tmp/.paddlex 2>/dev/null || true
    chmod -R 755 /tmp/.paddlex 2>/dev/null || true

    # Create XDG cache directory in /tmp (tmpfs is writable even with read_only: true)
    mkdir -p /tmp/.cache
    chown -R ocruser:ocruser /tmp/.cache 2>/dev/null || true
    chmod -R 755 /tmp/.cache 2>/dev/null || true

    # Also ensure /tmp/ocr_uploads is accessible
    mkdir -p /tmp/ocr_uploads
    chown -R ocruser:ocruser /tmp/ocr_uploads 2>/dev/null || true
    chmod -R 755 /tmp/ocr_uploads 2>/dev/null || true
else
    # If not root, try to create directories (might fail, but that's okay)
    mkdir -p /tmp/.paddlex/temp 2>/dev/null || true
    mkdir -p /tmp/.paddlex/official_models 2>/dev/null || true
    mkdir -p /tmp/.cache 2>/dev/null || true
    mkdir -p /tmp/ocr_uploads 2>/dev/null || true
fi

# Execute the original command as ocruser
# Use 'su ocruser' (not 'su - ocruser') to avoid full login shell
# PaddlePaddle environment and HOME are configured in Python code (ROOT CAUSE FIX)
if [ "$(id -u)" = "0" ]; then
    # Set environment variables and execute command as ocruser
    # PaddlePaddle cache directories and HOME are configured in Python before imports
    # TMPDIR and XDG_CACHE_HOME are in /tmp (writable tmpfs)
    cmd_string="cd /app && export TMPDIR=/tmp XDG_CACHE_HOME=/tmp/.cache PADDLEPADDLE_CACHE_DIR=/tmp/.paddlex && exec"
    for arg in "$@"; do
        cmd_string="$cmd_string '$arg'"
    done
    exec su ocruser -c "$cmd_string"
else
    exec "$@"
fi

