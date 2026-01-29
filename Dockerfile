# Use an official Python runtime
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    aria2 \
    curl \
    unzip \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and its dependencies
# We install them in one layer and clean up to keep the image small
RUN playwright install chromium && \
    playwright install-deps chromium && \
    rm -rf /var/lib/apt/lists/*

# Copy application code
COPY . .

# Create downloads directory
RUN mkdir -p /app/downloads

# Expose the port (Koyeb uses the PORT env var, but EXPOSE is good practice)
EXPOSE 8000

# Start command
# 1. Starts Aria2 daemon
# 2. Starts Main Python Bot
CMD aria2c \
    --enable-rpc \
    --rpc-listen-all=true \
    --rpc-allow-origin-all=true \
    --daemon \
    --max-connection-per-server=10 \
    --split=10 \
    --min-split-size=10M \
    --max-concurrent-downloads=5 \
    --bt-tracker="udp://tracker.opentrackr.org:1337/announce,udp://tracker.openbittorrent.com:80/announce,udp://opentracker.i2p.rocks:6969/announce,udp://tracker.internetwarriors.net:1337/announce,udp://tracker.leechers-paradise.org:6969/announce,udp://coppersurfer.tk:6969/announce,udp://tracker.zer0day.to:1337/announce" \
    && python main.py
