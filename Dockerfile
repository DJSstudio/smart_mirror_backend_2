# ------------------------------
# Smart Mirror Backend - Dockerfile
# ------------------------------

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Ensure important folders exist
RUN mkdir -p /app/db /app/media /app/keys

# Gunicorn port
EXPOSE 8000

# Run migrations & start gunicorn
CMD ["bash", "-c", "\
    python manage.py migrate && \
    gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 \
"]
