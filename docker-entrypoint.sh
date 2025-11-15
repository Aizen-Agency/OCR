#!/bin/bash
set -e

# Note: /home/ocruser is created in Dockerfile with correct permissions
# With read_only: true, we cannot modify /home/ocruser itself, only the volume mount

# Fix permissions for PaddleOCR model directory (volume is mounted at /home/ocruser/.paddlex)
# The volume is writable even with read_only: true, so we can create subdirectories
if [ "$(id -u)" = "0" ]; then
    # Ensure the .paddlex directory exists (volume mount point)
    # Create all required subdirectories that PaddleOCR needs
    mkdir -p /home/ocruser/.paddlex/temp
    mkdir -p /home/ocruser/.paddlex/official_models

    # Fix ownership on the volume (volumes are writable even with read_only: true)
    # This ensures ocruser can write to the volume-mounted directories
    chown -R ocruser:ocruser /home/ocruser/.paddlex 2>/dev/null || true
    chmod -R 755 /home/ocruser/.paddlex 2>/dev/null || true

    # Create cache directory in /tmp (tmpfs is writable even with read_only: true)
    # PaddleOCR will use XDG_CACHE_HOME=/tmp/.cache (set in environment)
    mkdir -p /tmp/.cache
    chown -R ocruser:ocruser /tmp/.cache 2>/dev/null || true
    chmod -R 755 /tmp/.cache 2>/dev/null || true

    # Also ensure /tmp/ocr_uploads is accessible
    mkdir -p /tmp/ocr_uploads
    chown -R ocruser:ocruser /tmp/ocr_uploads 2>/dev/null || true
    chmod -R 755 /tmp/ocr_uploads 2>/dev/null || true
else
    # If not root, try to create directories (might fail, but that's okay)
    mkdir -p /home/ocruser/.paddlex/temp 2>/dev/null || true
    mkdir -p /home/ocruser/.paddlex/official_models 2>/dev/null || true
    mkdir -p /tmp/.cache 2>/dev/null || true
    mkdir -p /tmp/ocr_uploads 2>/dev/null || true
fi

# Execute the original command as ocruser
# Use 'su ocruser' (not 'su - ocruser') to avoid full login shell
# Full login shell tries to write to /home/ocruser which fails with read_only: true
if [ "$(id -u)" = "0" ]; then
    # Set environment variables and execute command as ocruser
    # Use 'su' without '-' to avoid login shell that tries to write to home directory
    # Set TMPDIR and XDG_CACHE_HOME to /tmp which is writable (tmpfs mount)
    # XDG_CACHE_HOME redirects PaddleOCR's cache from /home/ocruser/.cache to /tmp/.cache
    # Build command string with proper quoting
    # Use HOME from environment if set, otherwise default to /home/ocruser
    home_dir="${HOME:-/home/ocruser}"
    cmd_string="cd /app && export HOME=$home_dir TMPDIR=/tmp XDG_CACHE_HOME=/tmp/.cache && exec"
    for arg in "$@"; do
        cmd_string="$cmd_string '$arg'"
    done
    exec su ocruser -c "$cmd_string"
else
    exec "$@"
fi

