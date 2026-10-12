FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TASTE_HOST=0.0.0.0 \
    TASTE_PORT=8090 \
    TASTE_DB_PATH=/data/taste.db

WORKDIR /app

# The runtime user is created before the sources are copied so that COPY can
# hand them over with --chown. Without that, COPY preserves the build context's
# permissions, and a context whose files are not world-readable (this archive
# stores everything mode 0660) produces an image that builds cleanly and then
# fails at startup with "Permission denied" on the entrypoint script. See the
# same idiom in king-of-meal-prep's Dockerfile.
RUN addgroup --system taste && adduser --system --ingroup taste taste \
    && mkdir -p /data && chown taste:taste /data

COPY --chown=taste:taste local_api.py local_catalog.json ./

USER taste

VOLUME ["/data"]
EXPOSE 8090
CMD ["python", "local_api.py"]
