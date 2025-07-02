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
    nodejs \
    npm

# --- Backend Setup ---
WORKDIR /app
COPY requirements.txt .
RUN pip3 install --break-system-packages --no-cache-dir -r requirements.txt
COPY WW-main.py .

# --- Frontend Setup ---
WORKDIR /frontend_build

# Copy React dependencies first to use cache if unchanged
COPY frontend_src/package*.json ./
RUN echo "=== Running npm install ===" && npm install

# Copy remaining frontend source
COPY frontend_src/ ./

# Build React app
RUN echo "=== Running npm run build ===" && npm run build

# List the output of the React build
RUN echo "=== Contents of /frontend_build/build ===" && ls -R /frontend_build/build

# --- Copy React Build Output into Flask Static Folder ---
WORKDIR /app
RUN mkdir -p /app/frontend && \
    cp -r /frontend_build/build/* /app/frontend/ && \
    echo "=== Contents of /app/frontend ===" && ls -R /app/frontend

# --- Add Startup Script ---
COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
