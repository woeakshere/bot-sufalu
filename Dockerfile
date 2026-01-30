# Use an official Python runtime
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
# Essential for automatic dependency installation
ENV DEBIAN_FRONTEND=noninteractive

# 1. Install Core System Tools & Downloader
# We only install the basics here. Playwright will handle the browser libs later.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    aria2 \
    curl \
    git \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# 2. Install Python Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Install Chromium & System Dependencies
# 'install-deps' checks the exact browser version and installs 
# the correct missing libraries (libnss, libatk, etc.) automatically.
RUN playwright install chromium
RUN playwright install-deps chromium

# 4. Copy application code
COPY . .

# --- CLEANUP ---
# Keeps the image small
RUN rm -rf /app/downloads /app/__pycache__ /app/.git /app/.github /app/bot/__pycache__ /app/utils/__pycache__ && \
    mkdir -p /app/downloads

# Expose the port
EXPOSE 8000

# --- STARTUP COMMAND ---
# 1. Kill old Aria2 zombies
# 2. Clean download folder
# 3. Start Aria2 Daemon (Fixed tracker string format)
# 4. Start Python Bot
CMD pkill -f aria2c || true && \
    rm -rf /app/downloads/* && \
    aria2c \
    --enable-rpc \
    --rpc-listen-all=true \
    --rpc-allow-origin-all=true \
    --daemon \
    --max-connection-per-server=10 \
    --split=10 \
    --min-split-size=10M \
    --max-concurrent-downloads=5 \
    --bt-tracker="udp://tracker.opentrackr.org:1337/announce,udp://tracker.openbittorrent.com:80/announce,udp://opentracker.i2p.rocks:6969/announce,udp://tracker.internetwarriors.net:1337/announce,udp://tracker.leechers-paradise.org:6969/announce,udp://coppersurfer.tk:6969/announce,udp://tracker.zer0day.to:1337/announce" \
    && exec python main.py
