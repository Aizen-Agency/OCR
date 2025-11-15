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
    mkdir -p /home/ocruser/.cache

    # Fix ownership on the volume (volumes are writable even with read_only: true)
    # This ensures ocruser can write to the volume-mounted directories
    chown -R ocruser:ocruser /home/ocruser/.paddlex 2>/dev/null || true
    chown -R ocruser:ocruser /home/ocruser/.cache 2>/dev/null || true
    chmod -R 755 /home/ocruser/.paddlex 2>/dev/null || true
    chmod -R 755 /home/ocruser/.cache 2>/dev/null || true

    # Also ensure /tmp/ocr_uploads is accessible
    mkdir -p /tmp/ocr_uploads
    chown -R ocruser:ocruser /tmp/ocr_uploads 2>/dev/null || true
    chmod -R 755 /tmp/ocr_uploads 2>/dev/null || true
else
    # If not root, try to create directories (might fail, but that's okay)
    mkdir -p /home/ocruser/.paddlex/temp 2>/dev/null || true
    mkdir -p /home/ocruser/.paddlex/official_models 2>/dev/null || true
    mkdir -p /home/ocruser/.cache 2>/dev/null || true
    mkdir -p /tmp/ocr_uploads 2>/dev/null || true
fi

# Execute the original command as ocruser
# Use 'su ocruser' (not 'su - ocruser') to avoid full login shell
# Full login shell tries to write to /home/ocruser which fails with read_only: true
if [ "$(id -u)" = "0" ]; then
    # Set HOME explicitly and change to /app, then execute command
    # Use 'su' without '-' to avoid login shell that tries to write to home directory
    # Set TMPDIR to /tmp which is writable (tmpfs mount)
    exec su ocruser -s /bin/bash -c "export HOME=/home/ocruser && export TMPDIR=/tmp && cd /app && exec \"\$@\"" -- "$@"
else
    exec "$@"
fi

