# Deploying ENSA Project Manager

One Linux server (VPS), Docker Compose, automatic HTTPS. About 30 minutes the first time.

The production stack (`docker-compose.prod.yml`):

| Service     | What it does                                                               |
|-------------|----------------------------------------------------------------------------|
| `web`       | Django + gunicorn. Applies database migrations every time it starts.       |
| `scheduler` | Daily jobs: deadline reminders 08:00, digest 18:00, cleanup 03:00.          |
| `db`        | PostgreSQL 16 (volume `pgdata`).                                           |
| `caddy`     | HTTPS (Let's Encrypt certificates, renewed automatically) and `/media`.    |
| `backup`    | Nightly database dump + archive of uploaded files, 14 days kept.           |

Uploaded deliverables live in the `private` volume and are only ever served by Django
after a permission check; Caddy only sees public images (`media`).

---

## 1. Server

- Ubuntu 24.04 (or Debian 12), 2 vCPU, 2 GB RAM, 40 GB disk is plenty for a school year.
- Open ports 80 and 443 (and 22 for SSH). Nothing else.
- Install Docker Engine + the Compose plugin: https://docs.docker.com/engine/install/

```bash
sudo usermod -aG docker $USER   # then log out/in
docker compose version          # must print v2.x
```

## 2. DNS

Create an `A` record (and `AAAA` if the server has IPv6) for the domain, e.g.
`projets.ensa-kenitra.ma → <server IP>`. Wait until `dig +short projets.ensa-kenitra.ma`
returns the IP: Caddy needs it to obtain the certificate.

## 3. Code and configuration

```bash
git clone <repository URL> ensa-projects && cd ensa-projects
cp .env.prod.example .env
nano .env
```

Fill in `.env`:

| Variable | Value |
|---|---|
| `DOMAIN` | the domain from step 2, without `https://` |
| `POSTGRES_PASSWORD` | a long random string (`openssl rand -base64 32`) |
| `DJANGO_SECRET_KEY` | `python3 -c "import secrets; print(secrets.token_urlsafe(64))"` — ≥ 50 characters |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | SMTP account (school mail server, Brevo, Mailgun, Gmail app password…) |
| `DEFAULT_FROM_EMAIL` | e.g. `Projets ENSA <noreply@ensa-kenitra.ma>` |
| `ADMINS` | who receives server error emails: `Name <email>` |
| `SENTRY_DSN` | optional, error tracking |

Keep `.env` out of git (it is in `.gitignore`) and readable only by you: `chmod 600 .env`.

## 4. First start

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps          # all services "running"/"healthy"
docker compose -f docker-compose.prod.yml logs -f web # Ctrl-C to stop following
```

Open `https://<DOMAIN>/healthz` — it answers `{"status": "ok", "database": "ok"}` once the
app and the database are up.
The first certificate can take a minute.

## 5. Administrator account

```bash
docker compose -f docker-compose.prod.yml run --rm web manage createadmin \
  --username admin.projets --email admin@ensa-kenitra.ma
```

The password is printed **once**: store it in a password manager, then log in and change
it (menu → Mot de passe). Teachers and students sign up themselves; the administrator
approves them under *Inscriptions*, or imports them from Excel under *Utilisateurs*.

The Django admin (low-level data access) is at `/gestion-interne/` (`ADMIN_URL` to change).

## 6. Check email

```bash
docker compose -f docker-compose.prod.yml run --rm web manage check_email you@example.com
```

If it fails, the error message comes from the SMTP server: wrong password, sender address
not allowed, or the port. Port 587 uses `EMAIL_USE_TLS=True` (the default); port 465 needs
`EMAIL_PORT=465` and `EMAIL_USE_SSL=True`.

## 7. Backups and a restore drill

Backups are written every night to the `backups` volume:

```bash
docker compose -f docker-compose.prod.yml exec backup ls -lh /backups
```

**Copy them off the server** (a volume on the same disk does not survive a lost server):

```bash
docker compose -f docker-compose.prod.yml cp backup:/backups ./backups-$(date +%F)
# then e.g. rsync/rclone ./backups-* to another machine or storage bucket
```

Restore drill (do it once, on a test machine, before you need it):

```bash
# database
docker compose -f docker-compose.prod.yml stop web scheduler
docker compose -f docker-compose.prod.yml cp ./db_YYYY-MM-DD_HHMM.dump db:/tmp/restore.dump
docker compose -f docker-compose.prod.yml exec db \
  pg_restore --clean --if-exists -U ensa -d ensa /tmp/restore.dump
# uploaded files
docker compose -f docker-compose.prod.yml cp ./files_YYYY-MM-DD_HHMM.tar.gz web:/tmp/files.tar.gz
docker compose -f docker-compose.prod.yml exec -u root web \
  sh -c "tar -xzf /tmp/files.tar.gz -C /data && chown -R app:app /data/media /data/private"
docker compose -f docker-compose.prod.yml start web scheduler
```

## 8. Upgrades

```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build   # migrations run on start
docker compose -f docker-compose.prod.yml logs --tail 50 web
```

## 9. Rollback

```bash
git log --oneline -5                      # find the previous good commit
git checkout <commit>
docker compose -f docker-compose.prod.yml up -d --build
```

If the bad release changed the database schema, restore the last backup taken before the
upgrade (step 7) — migrations are not rolled back automatically.

## Local rehearsal

The same stack runs on a laptop with a self-signed certificate:

```bash
DOMAIN=localhost HTTP_PORT=8080 HTTPS_PORT=8443 \
  docker compose -f docker-compose.prod.yml up -d --build
# https://localhost:8443 (accept the local certificate warning)
```
