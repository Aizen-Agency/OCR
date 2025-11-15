#!/bin/bash
set -e

# Fix permissions for PaddleOCR model directory if volume is mounted
if [ -d "/home/ocruser/.paddlex" ]; then
    # Create subdirectories if they don't exist
    mkdir -p /home/ocruser/.paddlex/temp
    mkdir -p /home/ocruser/.paddlex/official_models
    
    # Fix ownership (only if running as root, which we are in entrypoint)
    if [ "$(id -u)" = "0" ]; then
        chown -R ocruser:ocruser /home/ocruser/.paddlex
        chmod -R 755 /home/ocruser/.paddlex
    fi
fi

# Execute the original command as ocruser
# Use su to switch to ocruser and execute the command
if [ "$(id -u)" = "0" ]; then
    exec su - ocruser -c "cd /app && exec \"\$0\" \"\$@\"" -- "$@"
else
    exec "$@"
fi

