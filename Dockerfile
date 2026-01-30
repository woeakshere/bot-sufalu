# Use a specific, stable Debian version (Bookworm) to prevent package name errors
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV DEBIAN_FRONTEND=noninteractive

# 1. Install System Tools & Manual Chromium Dependencies
# We skip 'playwright install-deps' because it is buggy on Debian.
# These packages are HARDCODED to ensure Chromium runs on Debian Bookworm.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    aria2 \
    curl \
    git \
    procps \
    # --- Browser Support Libs ---
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
    fonts-liberation \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Install Python Deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Install Chromium Browser Only (Deps are already installed above)
RUN playwright install chromium

# 4. Copy Code
COPY . .

# --- CLEANUP ---
# Removes junk to keep image small
RUN rm -rf /app/downloads /app/__pycache__ /app/.git /app/.github /app/bot/__pycache__ /app/utils/__pycache__ && \
    mkdir -p /app/downloads

EXPOSE 8000

# --- STARTUP COMMAND ---
# 1. Kill old Aria2 zombies
# 2. Clean download folder
# 3. Start Aria2 Daemon
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
