FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y \
    netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy entrypoint script
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Copy project
COPY . .

# Create staticfiles directory
RUN mkdir -p staticfiles

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

# Run gunicorn
CMD gunicorn pantau_tular.wsgi:application --bind 0.0.0.0:${PORT:-8000} 