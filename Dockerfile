# Backend API image. Started by docker-compose.yml together with the database and web server.
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# tzdata gives zoneinfo the clinic timezone even if the base image has no system time zones.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt tzdata

COPY main.py .
COPY app ./app

RUN useradd --create-home clinic
USER clinic

EXPOSE 8000

# Only the web container can reach this port, so it may pass on the client address it sees.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
