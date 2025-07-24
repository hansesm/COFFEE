FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better cache layers
COPY requirements.txt /app/

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Create django user early
RUN adduser --disabled-password --gecos '' django

# Copy application code
COPY . /app

# Collect static files
RUN python manage.py collectstatic --noinput

# Change ownership of the app directory to django user
RUN chown -R django:django /app

# Switch to non-root user
USER django

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/', timeout=10)" || exit 1

CMD ["gunicorn", "--config", "gunicorn-cfg.py", "core.wsgi"]
