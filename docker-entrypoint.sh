#!/bin/bash
set -e

# Ensure /home/ocruser exists and has correct permissions
# This directory should exist from Dockerfile, but ensure it's accessible
if [ "$(id -u)" = "0" ]; then
    # Create /home/ocruser if it doesn't exist (should exist from Dockerfile)
    if [ ! -d "/home/ocruser" ]; then
        mkdir -p /home/ocruser
    fi
    chown ocruser:ocruser /home/ocruser
    chmod 755 /home/ocruser
fi

# Fix permissions for PaddleOCR model directory (volume is mounted at /home/ocruser/.paddlex)
# The volume mount will create /home/ocruser/.paddlex if it doesn't exist
# Create subdirectories that PaddleOCR needs
if [ "$(id -u)" = "0" ]; then
    mkdir -p /home/ocruser/.paddlex/temp
    mkdir -p /home/ocruser/.paddlex/official_models
    chown -R ocruser:ocruser /home/ocruser/.paddlex
    chmod -R 755 /home/ocruser/.paddlex
else
    # If not root, try to create directories (might fail, but that's okay)
    mkdir -p /home/ocruser/.paddlex/temp 2>/dev/null || true
    mkdir -p /home/ocruser/.paddlex/official_models 2>/dev/null || true
fi

# Execute the original command as ocruser
# Use su to switch to ocruser and execute the command
if [ "$(id -u)" = "0" ]; then
    exec su - ocruser -c "cd /app && exec \"\$0\" \"\$@\"" -- "$@"
else
    exec "$@"
fi

