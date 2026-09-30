# Operating ENSA Project Manager

Day-to-day tasks once the app is deployed (see [DEPLOY.md](DEPLOY.md)). Every command runs
from the project directory on the server; `dc` below stands for
`docker compose -f docker-compose.prod.yml`:

```bash
alias dc='docker compose -f docker-compose.prod.yml'
```

## Scheduled jobs

The `scheduler` container runs these once a day (Africa/Casablanca time). If it was down at
the scheduled time, the job runs as soon as it is back, the same day; a job never runs twice
in a day (state in the `appstate` volume).

| Time  | Job | What |
|-------|-----|------|
| 03:00 | `clearsessions` | delete expired login sessions |
| 03:15 | `axes_reset_failure_logs --age 30` | forget failed-login records older than 30 days |
| 08:00 | `send_deadline_reminders` | in-app + email reminders at J-7, J-3, J-1 and J-0 for students who still have work to do |
| 18:00 | `send_daily_digest` | one summary email for students who chose the daily digest |
| every 24 h* | backup (separate `backup` container) | database dump + uploaded files, 14 days kept |

\*The backup runs once when its container starts, then every 24 h after that.

Run a job by hand (e.g. to check it):

```bash
dc run --rm web manage send_deadline_reminders --dry-run
dc run --rm web manage send_daily_digest --dry-run
dc exec scheduler python manage.py run_scheduler --once   # whatever is due now
```

## Logs

```bash
dc logs -f web          # requests + application errors
dc logs -f scheduler    # daily jobs
dc logs --tail 100 caddy
dc logs backup          # "[backup] … done" every night
```

Server errors (HTTP 500) are also emailed to `ADMINS` and, if `SENTRY_DSN` is set, sent to
Sentry with the request details.

## Health

- `https://<DOMAIN>/healthz` → `{"status": "ok", "database": "ok"}` (HTTP 503 if the database
  is unreachable). Point an uptime monitor at it (UptimeRobot, Better Stack…).
- `dc ps` shows each container's health.

## Common tasks

| Task | How |
|------|-----|
| Approve sign-ups | in the app: *Inscriptions* (the badge shows how many are waiting) |
| Import students or teachers | *Utilisateurs* → *Importer* — download the Excel template there |
| Block an account | *Utilisateurs* → *Désactiver* (the person can no longer log in; data is kept) |
| Reset someone's password | they use *Mot de passe oublié ?* on the login page; or, as a last resort: `dc run --rm web manage changepassword <username>` |
| Another administrator | `dc run --rm web manage createadmin --username <name> --email <email>` |
| Unlock an account after too many failed logins | `dc run --rm web manage axes_reset_username <username>` (locks lift by themselves after 15 minutes) |
| Moderate the showcase | *Signalements*: hide, restore or dismiss reported projects |
| Test email settings | `dc run --rm web manage check_email you@example.com` |
| Django shell | `dc run --rm web manage shell` |

## Disk space

```bash
docker system df                     # images, volumes
dc exec backup du -sh /backups
docker image prune -f                # old images after upgrades
```

Uploads are capped at 10 MB per deliverable and 5 MB per image.

## Rotating secrets

| Secret | Steps | Effect |
|--------|-------|--------|
| `DJANGO_SECRET_KEY` | new value in `.env` → `dc up -d` | everyone is logged out; password-reset links already sent stop working |
| `POSTGRES_PASSWORD` | `dc exec db psql -U ensa -c "ALTER USER ensa PASSWORD 'new'"` → same value in `.env` → `dc up -d` | none if done in this order |
| SMTP password | update `EMAIL_HOST_PASSWORD` in `.env` → `dc up -d web scheduler` → `check_email` | none |
| Administrator password | in the app: menu → *Mot de passe* | — |

## Security settings worth knowing

- Content Security Policy is **enforced**. If a new feature is blocked in the browser (console
  shows "Content Security Policy"), set `CSP_ENFORCE=False` temporarily to switch to
  report-only, fix the cause (no inline scripts/styles, no third-party hosts), then turn it
  back on.
- Logins are rate-limited (django-axes): 5 failures lock the username + IP pair for 15
  minutes (`AXES_FAILURE_LIMIT`, `AXES_COOLOFF_MINUTES`).
- HSTS is on (1 year). `DJANGO_HSTS_PRELOAD=True` only if the whole domain will stay HTTPS
  forever — it is very hard to undo.
