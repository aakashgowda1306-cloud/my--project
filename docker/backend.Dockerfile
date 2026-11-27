# FastAPI backend image. Build from the repo root:
#   docker build -f docker/backend.Dockerfile -t cybersec-academy-api .
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
# The app reads lab datasets, lesson content and migrations from the repo layout.
COPY backend/app backend/app
COPY database database
COPY labs labs
COPY educational-content educational-content
WORKDIR /srv/backend
# Run as an unprivileged user, never as root.
RUN useradd --create-home --uid 10001 app
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
