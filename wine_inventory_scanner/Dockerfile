ARG BUILD_FROM
FROM $BUILD_FROM

# Install system dependencies
# Removed nodejs and npm as they are no longer needed
RUN apk add --no-cache \
    python3 \
    py3-pip \
    bash \
    sqlite-libs \
    gcc \
    python3-dev \
    libxml2-dev \
    libxslt-dev \
    zlib-dev

# --- Backend Setup ---
WORKDIR /app
COPY requirements.txt .
RUN pip3 install --break-system-packages --no-cache-dir -r requirements.txt
COPY WW-main.py .

# --- Frontend Setup ---
# Copy the new 'frontend' directory containing your static index.html
# This assumes you have already created wine_inventory_scanner/frontend/index.html
COPY frontend/ /app/frontend/

# --- Add Startup Script ---
COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]