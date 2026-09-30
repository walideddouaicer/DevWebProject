# ENSA Project Manager — production image (PLAN P4.6)
# One image, several roles (see docker/entrypoint.sh): web | scheduler | manage <cmd>

FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

# ---- dependencies in an isolated virtualenv ----
FROM base AS deps
RUN python -m venv /venv
COPY requirements/ requirements/
RUN /venv/bin/pip install -r requirements/prod.txt

# ---- runtime ----
FROM base AS runtime
ENV PATH="/venv/bin:$PATH" \
    ENVIRONMENT=prod \
    STATIC_ROOT=/app/staticfiles \
    MEDIA_ROOT=/data/media \
    PRIVATE_MEDIA_ROOT=/data/private \
    SCHEDULER_STATE_FILE=/data/scheduler.json

RUN groupadd --system app && useradd --system --gid app --home /app app \
    && mkdir -p /data/media /data/private /data/state && chown -R app:app /data

COPY --from=deps /venv /venv
COPY --chown=app:app . .

# Static files are collected at build time (hashed + compressed by WhiteNoise). The
# throwaway values only satisfy the production settings guard rails for this step.
RUN DJANGO_SECRET_KEY=build-only-$(python -c "print('x'*60)") \
    DJANGO_ALLOWED_HOSTS=build SITE_URL=https://build.invalid \
    python manage.py collectstatic --noinput --verbosity 0 \
    && chmod +x docker/entrypoint.sh

USER app
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status == 200 else 1)"

ENTRYPOINT ["docker/entrypoint.sh"]
CMD ["web"]
