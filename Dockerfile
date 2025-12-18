FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend backend
COPY frontend frontend
COPY readme.md ./
COPY docker-entrypoint.sh ./

RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8000 8001

ENTRYPOINT ["/app/docker-entrypoint.sh"]
