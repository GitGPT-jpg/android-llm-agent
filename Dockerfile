FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for EasyOCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py auto_reply.py ./
COPY config/ config/
COPY persona/ persona/
COPY scripts/ scripts/

# ADB is not bundled in the image; mount or install it at runtime
# See README for ADB USB passthrough setup with Docker

CMD ["python", "main.py"]
