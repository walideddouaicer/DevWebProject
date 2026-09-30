#!/bin/sh
# Container roles (PLAN P4.6):
#   web        wait for the DB, apply migrations, serve with gunicorn
#   scheduler  wait for the DB, run the daily jobs forever
#   manage ... any manage.py command, e.g. `manage createadmin`
set -e

case "$1" in
  web)
    python manage.py wait_for_db
    python manage.py migrate --noinput
    exec gunicorn ensa_project_manager.wsgi:application \
      --bind 0.0.0.0:8000 \
      --workers "${GUNICORN_WORKERS:-3}" \
      --timeout "${GUNICORN_TIMEOUT:-60}" \
      --max-requests 1000 --max-requests-jitter 100 \
      --forwarded-allow-ips "*" \
      --control-socket /tmp/gunicorn.ctl \
      --access-logfile - --error-logfile -
    ;;
  scheduler)
    python manage.py wait_for_db
    exec python manage.py run_scheduler
    ;;
  manage)
    shift
    exec python manage.py "$@"
    ;;
  *)
    exec "$@"
    ;;
esac
