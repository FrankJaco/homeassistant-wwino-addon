ARG BUILD_FROM
FROM $BUILD_FROM

# Install system dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    bash \
    sqlite-libs \
    gcc \
    python3-dev \
    libxml2-dev \
    libxslt-dev \
    zlib-dev \
    chromium \
    chromium-chromedriver

# --- Backend Setup ---
WORKDIR /app
COPY requirements.txt .
RUN pip3 install --break-system-packages --no-cache-dir -r requirements.txt
COPY app/ /app/app/ 

# --- Frontend Setup ---
COPY frontend/ /app/frontend/

# --- Add Startup Script ---
COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
