# Use an official Python runtime
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Install system dependencies
# 1. Core tools (ffmpeg, aria2, etc.)
# 2. Chromium dependencies (replacing broken 'playwright install-deps')
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    aria2 \
    curl \
    unzip \
    gcc \
    python3-dev \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Chromium Browser only (We already installed deps above)
RUN playwright install chromium

# Copy application code
COPY . .

# Create downloads directory
RUN mkdir -p /app/downloads

# Expose the port
EXPOSE 8000

# Start command with Speed Optimizations & Trackers
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
