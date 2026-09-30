# CLAUDE.md

> **ACTIVE WORK: `PLAN.md` is the master plan (production readiness + full UI revamp).**
> The user delegated it fully and will only say "continue". Every session: follow
> `PLAN.md` §0 (session protocol): branch `revamp`, next unchecked task, `make check`,
> commit, update PLAN §1 + §9 log. Ask the user nothing outside PLAN §7.

## Project

**ENSA Project Manager** — Django 5.2 LTS platform for engineering-school student projects.
Roles: student, teacher, administrator (+ anonymous visitors of the public showcase).
Server-rendered templates; UI copy is **French**, code is English.

## Commands (Linux)

```bash
make setup          # .venv + requirements/dev.txt + migrate
make run            # runserver
make check          # ruff, django checks (incl. --deploy with fake prod env), migrations, tests
make test           # test suite only (excludes the e2e tag)
make e2e            # Playwright browser journeys in e2e/ (live server, seeded DB)
make qa             # screenshot every page x role; fails on JS/CSP errors or serious axe issues
make seed           # demo data (password for every account: demo12345!)
.venv/bin/python manage.py seed_demo --reset   # wipe DB + reseed (DEBUG only)
```

Demo logins after `make seed`: `admin`, `prof.alami` (WEB401, IA501), `prof.bennani`,
`etu.amine`, `etu.salma`, `etu.youssef` (owns a 3-person team), `etu.anas` (no team) …

Throwaway DB: `DB_ENGINE=django.db.backends.sqlite3 DB_NAME=/tmp/x.sqlite3 …`.
Postgres check: `docker run -d --rm --name ensa-pg-test -e POSTGRES_DB=ensa -e POSTGRES_USER=ensa
-e POSTGRES_PASSWORD=ensa -p 55432:5432 postgres:16-alpine`, then run with `DB_ENGINE=
django.db.backends.postgresql DB_NAME=ensa DB_USER=ensa DB_PASSWORD=ensa DB_HOST=127.0.0.1 DB_PORT=55432`.

## Layout

| App | Responsibility |
|---|---|
| `public` | Landing pages + public showcase (views, likes, comments, reports) |
| `accounts` | Signup → `PendingRegistration` → admin approval |
| `student` | Core domain: `Project` and everything around it (deliverables, milestones, invitations, notifications, assignments from the student side, calendar) |
| `teacher` | Modules, enrollments, `ProjectAssignment`/`ProjectOption`/`DirectStudentAssignment`, review, grading (`ProjectEvaluation`), announcements |
| `administrator` | Admin dashboard, users/imports, modules, moderation, exports, `seed_demo` |
| `search` | Role-aware global search |
| `ui` | Design system: template tags (`icon`, `status_chip`, `avatar`, `field`…), navigation, widgets, styleguide (DEBUG) |
| `tests/` | Cross-app suites: `test_smoke.py` (every URL × role: no 5xx, no GET mutation, permission matrix, outsider POSTs), `test_regressions.py` (bug ids from PLAN §3) |
| `e2e/` | Browser journeys (tag `e2e`): `BrowserTestCase` in `e2e/base.py`; failure screenshots in `e2e/artifacts/` |
| `docs/` | `DEPLOY.md` (server setup), `OPERATIONS.md` (jobs, logs, secrets) |

UI rules: CSS sources in `assets/css/**` built into `static/css/app.css` by
`scripts/build_css.py` (commit both). No inline `style`/`on*`/`<script>` anywhere (the CSP
is enforced; widget attrs are tested too), no CDN. Emails: `templates/emails/<name>.txt` +
`.html`, sent with `ensa_project_manager.emails.send_templated_email`, gated by `wants_email`.

Role = which `*Profile` row a User has (Admin > Teacher > Student, see `ensa_project_manager/views.py`).

## Conventions

- **Fat models**: domain logic on models (state transitions, team rules), views stay thin.
- Match surrounding language: French UI strings, English identifiers.
- Every fix gets a test. Removing a bug's `@expectedFailure` in `tests/test_regressions.py` and
  its `KNOWN_FAILURES` entries in `tests/test_smoke.py` is part of fixing it.
- `ProjectOption` claiming uses `select_for_update()` — preserve that pattern.
- N+1 risk in list views: use `select_related`/`prefetch_related`/annotations.
- Settings are env-driven (`ensa_project_manager/settings.py`, `.env` auto-loaded in dev).
- Commits end with the Co-Authored-By trailer. Never push without the user's OK (PLAN §7).
