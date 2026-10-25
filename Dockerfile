# =====================================================================
# Autonomous AI Outreach Engine - Production Dockerfile
# =====================================================================
FROM python:3.11-slim-bullseye

# Prevent python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system dependencies & fonts for Typst PDF rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    fonts-liberation \
    fonts-dejavu-core \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium headless for ATS verification
RUN playwright install chromium --with-deps

# Copy application code
COPY . .

# Create data directories
RUN mkdir -p data/resumes data/cache

# Default command
CMD ["python", "run_agent.py", "--dry-run"]
