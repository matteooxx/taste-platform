FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TASTE_HOST=0.0.0.0 \
    TASTE_PORT=8090 \
    TASTE_DB_PATH=/data/taste.db

WORKDIR /app
COPY local_api.py local_catalog.json ./
RUN addgroup --system taste && adduser --system --ingroup taste taste \
    && mkdir -p /data && chown taste:taste /data
USER taste

VOLUME ["/data"]
EXPOSE 8090
CMD ["python", "local_api.py"]
