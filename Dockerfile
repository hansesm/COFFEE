FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip to latest version (fixes CVE-2025-8869)
RUN pip install --upgrade pip

# Install uv
RUN pip install uv

# Copy requirements first for better cache layers
COPY pyproject.toml uv.lock ./

# Install Python dependencies
RUN uv sync --frozen

# Create django user early
RUN adduser --disabled-password --gecos '' django

# Copy application code
COPY . /app

# Collect static files
RUN uv run task collect-static

# Change ownership of the app directory to django user
RUN chown -R django:django /app

# Switch to non-root user
USER django

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/', timeout=10)" || exit 1

CMD ["uv", "run", "task", "prod"]
