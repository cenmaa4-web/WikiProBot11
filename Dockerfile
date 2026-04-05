FROM node:20-slim

# Install system dependencies: Python3, pip, ffmpeg
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    ffmpeg \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install yt-dlp (latest version)
RUN pip3 install --no-cache-dir yt-dlp

# Verify yt-dlp works
RUN yt-dlp --version

WORKDIR /app

# Copy package files first (for Docker cache)
COPY package.json ./
RUN npm install --production

# Copy source code
COPY src/ ./src/

# Create temp directory for downloads
RUN mkdir -p /tmp/bot-downloads

EXPOSE 3000

CMD ["node", "src/index.js"]
