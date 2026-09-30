# PLAN — ENSA Project Manager → production-ready + full UI revamp

Master plan written 2026-09-30 after a full review (see "Review findings" below).
**Owner of execution: Claude, autonomously, across many sessions.** The user will not
read this file or answer questions mid-task; they will open a session and press Enter.
This file is the single source of truth. `ROADMAP.md` is historical (v1 feature backlog).

---

## 0. SESSION PROTOCOL (read this first, every session)

1. Read `CLAUDE.md`, then this file's **§1 Current state** and the last 3 entries of **§9 Log**.
2. `cd /home/walideddouicer/Work/DevWebProject && git status && git branch --show-current`
   - Work on branch **`revamp`**. Never commit to `main` directly. Never force-push.
   - If the tree is dirty from an interrupted session: inspect the diff, finish or revert
     the half-done task, and note what happened in the log.
3. Activate env: `source .venv/bin/activate` (create it with §2 if missing).
4. Run the baseline `make check`. If it's red and the log doesn't explain why, fix that first.
5. Pick the **first unchecked task** in §5 (or the one marked `[~]` in progress). Follow
   its steps and satisfy its **Done when** criteria completely. No partial ticks.
6. After each task:
   - Run `make check` (must be green). For UI tasks also run `make screens` and **look at
     the screenshots** (Read tool on the PNGs) before calling it done.
   - Commit: `PLAN <id>: <summary>` + the Co-Authored-By trailer from the system prompt.
   - Tick the box here (`[x]`), update §1, append a §9 log entry
     (date · id · what changed · surprises · next). Commit that too (it can be the same commit).
7. Keep going task after task in the same session while context allows. Stop only at a
   clean boundary (everything committed, log updated).
8. **Never ask the user anything** except items in **§7 NEEDS-USER**, and only once all
   other work is done or blocked. For every other judgment call: decide, record it
   in §8 Decisions, move on. If a task is blocked on the user, mark it `[!]`, add it to §7,
   and continue with the next unblocked task.
9. Never push to GitHub, never deploy, and never create external accounts without the user's
   go-ahead (§7). Local commits only.
10. If reality contradicts this plan (a file moved, a step is wrong), fix the plan
    first (edit the task and note it in the log), then execute.

Status markers: `[ ]` todo · `[~]` in progress · `[x]` done · `[!]` blocked on user · `[-]` dropped (say why in the log).

---

## 1. CURRENT STATE

- Phase: **P7.2 done → P7.3 next (enforce CSP)**
- Branch: `revamp` (created from `main` @ `5c3597d`)
- Last green `make check`: 2026-09-30 (282 tests)
- Open NEEDS-USER items: none yet (deployment ones come at P8)

---

## 2. ENVIRONMENT (Linux, Arch; user's machine)

- Python on the machine: 3.14. Target runtime in Docker: **python:3.13-slim** (see D3).
- Setup (once):
  ```bash
  cd /home/walideddouicer/Work/DevWebProject
  python3 -m venv .venv && source .venv/bin/activate
  pip install -r requirements/dev.txt      # after P0.2; before that: see P0.2
  python manage.py migrate && python manage.py seed_demo   # seed_demo exists after P0.5
  ```
- Docker is installed (`/usr/bin/docker`). Node is available through mise (`node`, `npx`) but
  **only for dev tooling** (Playwright/axe). The app itself must never need Node.
- Demo logins (after P0.5; password for all: `demo12345!`): `admin`, `prof.alami`,
  `prof.bennani`, `etu.amine`, `etu.salma`, `etu.youssef`, … (see `seed_demo`).
- Throwaway DB for experiments: `DB_ENGINE=django.db.backends.sqlite3 DB_NAME=/tmp/…sqlite3`.
  Never touch a real `db.sqlite3` if one appears.

---

## 3. REVIEW FINDINGS (2026-09-30) — the bug inventory P1/P2 must close

All reproduced at runtime unless marked (unverified). IDs are referenced by tasks.

- **B1** Owner of a project with ≥2 collaborators gets a 500 (`MultipleObjectsReturned`) from
  `get_object_or_404(Project, Q(student)|Q(collaborators), id=…)`: student/views.py project_submit,
  upload_deliverable, add_milestone, add_comment, project_submit_confirmation.
- **B2** `ProjectForm.collaborators` (student/forms.py) lets the owner attach up to 10 students with
  no consent and no team-size/enrollment/one-project-per-assignment checks, on both create and edit.
- **B3** `/student/projects/<id>/status/<new_status>/` (project_change_status) submits and bypasses
  every submission rule.
- **B4** `student:project_approve` / `student:project_reject` let ANY teacher validate/reject ANY project.
- **B5** State changes on GET (CSRF-able): respond_to_invitation, project_submit, project_change_status,
  remove_collaborator, cancel_invitation, toggle/complete_milestone, leave_module,
  mark_notification(s)_read, teacher approve_project/reject_project, admin remove_assignment,
  remove_student_from_module, delete_profile_picture (partially), join_module (check).
- **B6** Deliverable allowlist includes .html/.svg/.js; media is served publicly with no access
  control; public project pages link every deliverable → stored XSS + data exposure.
- **B7** Missing templates → 500: administrator/{users_overview, students_list, teachers_list,
  statistics, module_oversight, module_status_confirm, recent_module_activity}.html,
  teacher/assignments/{students, teams}.html, public/explore_projects.html.
- **B8** Anonymous user on `/student/assignments/<id>/` → 500 (`requires_module_access` lacks login check).
- **B9** Approving a 2nd teacher with no teacher_id → IntegrityError (`teacher_id=''` on a unique field).
- **B10** `Project.calculate_progress()` ↔ `is_on_track()` infinite recursion (currently unused).
- **B11** `ProjectAssignment.get_completion_percentage` divides projects by students.
- **B12** Creating a direct assignment notifies students while it's still a draft; publishing notifies again.
- **B13** Students who enroll after an "all_students" direct assignment was created never get a
  DirectStudentAssignment → they can't start it.
- **B14** project_submit syncs DirectStudentAssignment only for the submitter; reject resets the whole team.
- **B15** (unverified) A student can change/clear `module` on an assignment project → it drops out of teacher scope.
- **B16** Approval email contains the literal `[URL_OF_YOUR_SITE]`.
- **B17** Signup ignores AUTH_PASSWORD_VALIDATORS.
- **B18** Teacher scoping is inconsistent: exports/bulk/progress use `assignment.teacher`, the rest use module membership.
- **B19** The pinned numpy 2.2.6 won't build on Python 3.14; matplotlib/numpy/contourpy/kiwisolver/
  fonttools/cycler/chardet/python-dateutil are unused.
- **B20** Hardcoded fallback SECRET_KEY; TIME_ZONE=UTC and LANGUAGE_CODE=en-us for a French/Moroccan
  app; no CACHES, no LOGGING; debug print() calls.
- **B21** Dead code: `webdevproject/` scaffold, 5 unregistered context processors, duplicate admin
  URL entries, `create_assignment_project` alias, legacy student-side approve/reject.
- **B22** No password-reset flow at all.
- **B23** Race: `report_count += 1`, `view_count += 1` (use F()).
- **B24** Likes/comments/reports allowed on projects hidden by an admin (they only check is_public).
- **B26** (found in P5.2 screenshots) Student dashboard stat cards show 0 projects while the
  table lists 2 (template/view variable mismatch). Fix in P6.3 (dashboard rebuilt).
- **B25** (found in P1.7) Stored XSS: user-controlled strings (deliverable names, collaborator
  names, module names, option titles) interpolated into inline `onclick`/`onsubmit` JS. HTML
  escaping is decoded by the browser before the JS runs. Patched with data attributes/`escapejs`
  in P1.7; P6 removes all inline handlers (P6.13 grep) and P7.3 enforces CSP.

---

## 4. TARGET ARCHITECTURE & STANDARDS (decisions are binding; rationale in §8)

**Backend**
- Django **5.2 LTS** (latest 5.2.x patch). Keep server-rendered templates. Keep the app layout.
- Settings: a single `ensa_project_manager/settings.py` driven by env vars (current style),
  plus `ENVIRONMENT=dev|test|prod`. In prod: fail fast on a missing SECRET_KEY, ALLOWED_HOSTS or DB.
- Roles: add `accounts/permissions.py` with `@student_required`, `@teacher_required`,
  `@admin_required` (they redirect anonymous users to login; 403 for the wrong role) and
  `get_project_for_member(student, project_id)` / `get_project_for_owner(...)` helpers.
  Every view uses them. No more ad-hoc `TeacherProfile.objects.get` try/except blocks.
- **Project state machine on the model** (fat-model convention): `Project.submit(by)`,
  `.validate(by_teacher)`, `.reject(by_teacher, reason)`, `.request_revision(by_teacher, text)`,
  `.reopen(by)`. Each is atomic, checks legality (raises ValidationError), writes
  ProjectActivity, syncs DirectStudentAssignment for the **whole team**, and sends notifications
  through one `notify_team()` helper. Every view (student, teacher single, bulk, grade) calls these.
  Delete the duplicated logic.
- Team membership changes ONLY through invitations → `Project.add_assignment_collaborator`.
- Mutating views: `@require_POST`. Templates submit small `<form method="post">` blocks.
- Files: deliverables go to a **private** storage location (`private/deliverables/…`), are
  never served by the web server, and are downloaded through `deliverable_download` views with
  permission checks (team, the module's teachers, admins; the public only for a public project
  when the owner explicitly allowed the file). Public images (avatars, covers) stay in public media.
- Notifications: keep the in-app Notification model; email through one `notifications/email.py`
  helper that respects preferences and digest mode.
- Packages to add (pin exact versions in requirements/*.txt): `whitenoise`, `gunicorn`,
  `psycopg[binary]`, `django-axes` (login throttling), `django-csp`, `sentry-sdk` (optional,
  env-gated), `django-htmx`. Dev: `ruff`, `coverage`, `playwright`, `django-debug-toolbar`, `factory-boy`.
  NO: DRF, Celery, React, Tailwind/Node build, jQuery, select2, Font Awesome, Chart.js via CDN.
- Scheduled jobs (`send_deadline_reminders`, `send_daily_digest`, `clearsessions`, backups):
  run by `supercronic` in a `cron` compose service.

**Frontend (see §6 for the design system)**
- One hand-written CSS design system in `static/css/` (tokens → base → components → layouts),
  no build step, served by WhiteNoise with a manifest. All per-page CSS files and inline
  `<style>` blocks are deleted by the end of P6.
- Interactivity: **HTMX** (vendored, `static/vendor/htmx.min.js`) plus tiny vanilla JS modules.
  No inline JS handlers (CSP-compatible: `script-src 'self'`).
- Icons: **Lucide** SVG sprite vendored at `static/icons/sprite.svg`, used through an
  `{% icon "name" %}` template tag. Fonts self-hosted (woff2) in `static/fonts/`.
- One base layout `templates/layouts/app.html` (authenticated shell, role-aware nav) and
  `templates/layouts/public.html`. Reusable pieces in `templates/components/*.html`
  (included with `{% include … with … only %}`) and a few simple inclusion tags.
- UI copy: French, sentence case, `vous`. `LANGUAGE_CODE='fr'`, `TIME_ZONE='Africa/Casablanca'`.
  (Full gettext/.po extraction is out of scope; see D9.)

**Quality gates (`make check` must pass after every task)**
- `ruff check` + `ruff format --check`, `manage.py check`, `check --deploy` (with prod env),
  `makemigrations --check`, the full test suite, and the **smoke test** (every URL × every role
  → no 5xx, and every GET that must not mutate doesn't).
- Coverage target ≥ 80% on `student`, `teacher`, `administrator`, `accounts` by the end of P7.

---

## 5. TASKS

### P0 — Safety net & tooling (do first; everything else depends on it)

- [x] **P0.1 Repo hygiene.** Delete `webdevproject/` (dead scaffold with its own secret; B21).
  Add to `.gitignore`: `.venv/`, `/private/`, `screens/`, `node_modules/`, `.coverage`, `htmlcov/`.
  Add `.editorconfig`. **Done when:** tree is clean and the app still runs.
- [x] **P0.2 Dependencies (B19).** Create `requirements/base.txt`, `prod.txt` (-r base + gunicorn,
  psycopg, sentry-sdk), `dev.txt` (-r base + ruff, coverage, playwright, debug-toolbar, factory-boy).
  Drop the unused scientific packages. Pin the latest Django 5.2.x and current versions that support
  Python 3.13 and 3.14. Keep the root `requirements.txt` as `-r requirements/prod.txt` for
  compatibility. **Done when:** a fresh `.venv` on Python 3.14 installs cleanly and 87 tests pass.
- [x] **P0.3 Ruff.** `pyproject.toml` with ruff config (line length 100, py313, rules E,F,I,B,UP,DJ,
  with migrations excluded). Run `ruff format` + safe fixes over the codebase in ONE commit, with no
  logic changes. Fix or `noqa` the remaining lint errors; bare `except:` → specific exceptions.
- [x] **P0.4 Makefile.** Targets: `setup`, `run`, `test`, `lint`, `check` (all quality gates in §4),
  `coverage`, `screens`, `seed`, `docker-build`, `docker-up`. `check` must exit non-zero on any failure.
- [x] **P0.5 `seed_demo` management command** (in `administrator/management/commands/`):
  idempotent, `--reset` flag. Creates realistic French/Moroccan data: 1 admin, 4 teachers,
  ~30 students across years 3–5, 5 modules, direct and choice-based assignments (team and
  individual, deadlines in the past/near/far), projects in every status, teams of 1–4, deliverables
  with versions (small generated PDFs/zip), milestones, comments, evaluations, public showcase
  projects with tags, likes, a few reports, pending registrations, notifications. Fixed RNG seed.
  Realistic names and titles, no lorem ipsum. **Done when:** `make seed` on an empty DB works
  twice in a row without errors.
- [x] **P0.6 Smoke test** `tests/test_smoke.py` (top-level `tests` package registered in settings or
  discovered through the runner): uses seed data (call `seed_demo` in setUpTestData, or a fast
  factory subset). Enumerates **every** URL pattern through the resolver, fills path args from real
  objects, and requests each as anon/student/owner-with-team/teacher/other-teacher/admin. Asserts
  no 5xx. For GET, snapshots row counts of key tables before/after and asserts unchanged
  (catches B5-type bugs). Known failures are allowed to start as `expectedFailure` with a B-id
  comment. **Done when:** the test runs, and each current failure is listed with its B-id.
- [x] **P0.7 Regression tests for B1–B24** in `tests/test_regressions.py`, one test per B-id,
  written to assert the CORRECT behavior and decorated `@expectedFailure` for now. Every fix task
  removes the decorator. (The old repro script's logic: owner with 2 collaborators → pages 200;
  status URL can't bypass; unrelated teacher gets 403/404; GET does not mutate; etc.)
- [x] **P0.8 CI file** `.github/workflows/ci.yml` (Python 3.13, Postgres 16 service, `make check`).
  Not pushed yet (needs the user; §7), but it must exist and work locally through `act`, or at least be valid YAML.
- [x] **P0.9 Update CLAUDE.md** (stale: "no tests", "search stubs", Windows paths) → Linux commands,
  a pointer to this PLAN and its protocol, and the new conventions from §4. Keep it short.

### P1 — Critical security & correctness (B1–B6, B8)

- [x] **P1.1 Permission layer.** `accounts/permissions.py` (decorators + project access helpers, §4).
  Unit tests for each decorator (anon → login redirect with `next`, wrong role → 403).
- [x] **P1.2 B1** Replace every `Q(student)|Q(collaborators)` + get pattern with the helpers
  (they use `.distinct()` / membership checks). grep: `Q(student=student) | Q(collaborators=student)`.
- [x] **P1.3 Project state machine** on the model (§4), with tests for each legal/illegal transition,
  deadline, team size, option required, team-wide DirectStudentAssignment sync (fixes **B14**),
  and notifications to the whole team.
- [x] **P1.4 B3/B4/B21-legacy** Delete `project_change_status`, `student:project_approve`,
  `student:project_reject`, and `student:add_feedback` (teacher feedback lives in the teacher app).
  Remove their URLs and template links; the "back to in progress" UX goes through
  `Project.reopen` in a POST view if it's still needed. Rewire teacher approve/reject/revision/
  bulk/grade to the state machine.
- [x] **P1.5 B2** Remove `collaborators` from ProjectForm (create and edit). Collaboration only
  through invitations. Also remove `module` from the edit form for assignment projects (B15)
  and validate `end_date >= start_date`.
- [x] **P1.6 B5** `@require_POST` on every mutating view (list in B5; re-grep for views that
  `.save()`/`.delete()`/`.update()` without a method check). Convert template links into POST forms
  (plain restyle is fine for now; P6 redesigns them). Smoke test's no-mutation-on-GET assertions pass.
- [x] **P1.7 B6 Private deliverables.** Separate storage: `DELIVERABLE_ROOT = BASE_DIR/'private'`
  (env-configurable) and a custom FileSystemStorage for `ProjectDeliverable.file`; a data
  migration that moves existing files. Download view `student:deliverable_download` /
  `teacher:…` / `public:…` with permission checks; `FileResponse(as_attachment=True)`, correct
  content type, `X-Content-Type-Options: nosniff`. Remove .html/.htm/.svg/.js/.xml from the
  allowlist (and zip bombs aren't our problem; size cap stays). Add a `Project.public_deliverables`
  opt-in (BooleanField, default False) that is shown in make-public. The public page lists files only if it's on.
  Also validate image uploads with Pillow (`Image.verify()`), not just the extension.
- [x] **P1.8 B8** All student assignment views use `@student_required`.
- [x] **P1.9 Login security.** django-axes (5 failures → 15 min lockout, keyed on username+IP),
  session security settings, logout via POST only (Django 5 requires it; check templates).

### P2 — Broken pages & logic bugs (B7, B9–B18, B22–B24)

- [x] **P2.1 B7 triage.** For each view with a missing template, decide: build it (it's linked
  and useful) or delete the view+URL+links. Default decisions: **build** admin statistics (merged into
  the dashboard/"Statistiques" page), admin users overview (redirect to `users_list`, delete
  students_list/teachers_list as separate views: users_list already has tabs), teacher
  assignment_students (needed for direct assignments), teacher assignment_teams (useful);
  **delete** public explore_projects (duplicate of the showcase → redirect), module_oversight,
  module_status_confirm, recent_module_activity (fold anything useful into existing pages). Record in §8.
  New templates use plain markup; P6 styles them.
- [x] **P2.2 B9** teacher_id/admin_id: store None, not ''. Data migration to convert '' → NULL.
- [x] **P2.3 B10** Fix the recursion: an `is_on_track` that doesn't call calculate_progress with
  is_on_track included (compute the progress parts once). Decide whether the progress bar is
  shown anywhere (P6 may use it); if not, delete both methods.
- [x] **P2.4 B11** Completion % = students covered by submitted/validated projects ÷ expected
  students (direct: DirectStudentAssignment count; choice: active enrollees).
- [x] **P2.5 B12/B13** No notifications/DirectStudentAssignment rows at draft creation for
  "all_students" — create them at publish. On a new enrollment (join_module, admin enroll),
  add DirectStudentAssignment rows for published "all_students" direct assignments of that module
  (a model method on ModuleEnrollment or a signal; prefer an explicit call in the enroll paths).
- [x] **P2.6 B18** Teacher access = module membership (ModuleAssignment active) everywhere;
  add `ProjectAssignment.is_manageable_by(teacher)`. Co-teachers can manage assignments.
- [x] **P2.7 B16/B17** Build absolute URLs from `SITE_URL` env (add to settings); the signup forms
  run `validate_password`. Emails move to templates `templates/emails/*.txt` (+ .html later in P6.12).
- [x] **P2.8 B22 Password reset** with Django's auth views, templates, email; a "Mot de passe oublié ?"
  link on login. Also add password change for teachers/admins (only students have it now).
- [x] **P2.9 B23/B24** F() expressions for counters; public interactions require
  `is_public=True, is_hidden_by_admin=False, status='validated'`.
- [x] **P2.10 Model hardening.** DB constraints: CheckConstraint min_team_size ≤ max_team_size,
  min ≥ 1; max_teams ≥ 1; score 0–20 on evaluations; conditional UniqueConstraints for
  nullable IDs. Indexes on Project(status), Project(module, status), Notification(recipient,
  is_read, created_at). Remove the `save()→clean()` override pitfalls if they block admin/bulk ops (keep the
  validation; call `full_clean` in forms). Migrations tested on a copy of seeded data.
- [x] **P2.11 Remove dead code (B21):** unregistered context processors, duplicate URL entries,
  aliases, "# Add this to your file" comment debris, runs of blank lines, debug `print()`s, and
  broad `except Exception` that swallow errors (log them instead).

### P3 — Code structure & performance

- [x] **P3.1 Split giant view modules** into packages: `student/views/{projects,deliverables,
  milestones,invitations,notifications,modules,profile,assignments,calendar}.py`, same for teacher
  and administrator. No behavior change; URLs unchanged; remove `from .x import *`.
- [x] **P3.2 Forms everywhere.** Replace `request.POST.get(...)` parsing in comments, announcements,
  revision requests, grading, and bulk actions with Django forms (validation, max lengths).
- [x] **P3.3 Query budget.** Add `assertNumQueries`-style tests (upper bounds) for: student
  dashboard, project detail, teacher dashboard, assignment progress, admin dashboard, admin users
  list, public showcase, search. Fix N+1s (the admin dashboard's per-module loop → annotate; teacher
  dashboard loop; get_team_statistics; comment `author_profile` lookups in loops).
- [x] **P3.4 Context processors.** One cheap badge-count processor per role, cached per user in
  the configured cache with explicit invalidation where notifications/invitations change
  (centralize in `notify_team`/invitation helpers). Remove the hour-bucket cache keys.
- [x] **P3.5 Pagination** on every unbounded list (notifications, users, projects, reports,
  showcase already has it, activities).

### P4 — Production configuration & deployment artifacts

- [x] **P4.1 Settings (B20).** `ENVIRONMENT` var; prod: required SECRET_KEY / ALLOWED_HOSTS /
  CSRF_TRUSTED_ORIGINS / DATABASE_URL-style vars (write a tiny parser; no new dependency needed),
  `LANGUAGE_CODE='fr'`, `TIME_ZONE='Africa/Casablanca'`, `CONN_MAX_AGE=60` + health checks,
  cache (DB cache table by default; Redis if `REDIS_URL` is set), `LOGGING` to stdout (JSON-ish
  single line in prod), `ADMINS` from env, `SERVER_EMAIL`, `DATA_UPLOAD_MAX_MEMORY_SIZE`,
  `FILE_UPLOAD_MAX_MEMORY_SIZE`, `SESSION_COOKIE_AGE`, `SECURE_REFERRER_POLICY`,
  `CSRF_COOKIE_HTTPONLY`. Remove the hardcoded fallback secret in prod mode (dev keeps a random per-run key).
  Update `.env.example` to be complete and commented.
- [x] **P4.2 Static & media.** WhiteNoise with `CompressedManifestStaticFilesStorage`; public
  media served by the reverse proxy from a volume; private deliverables are never proxied (P1.7).
- [x] **P4.3 CSP & headers.** django-csp: `default-src 'self'`; `img-src 'self' data:`;
  `style-src 'self'`; `script-src 'self'`; `frame-ancestors 'none'`; `form-action 'self'`.
  All inline scripts/styles gone by the end of P6 → set report-only now, enforce in P7.3.
- [x] **P4.4 Error pages & health.** Custom 400/403/404/500 templates (500 must be static-safe,
  no DB), `/healthz` (DB ping, returns JSON), `robots.txt` (disallow app areas, allow public),
  favicon + app icons, `security.txt`.
- [x] **P4.5 Sentry (optional).** Init only if `SENTRY_DSN` is set; send_default_pii False.
- [x] **P4.6 Dockerfile** (multi-stage, python:3.13-slim, non-root user, `pip install --no-cache`,
  `collectstatic` at build, `HEALTHCHECK`), `.dockerignore`, `docker/entrypoint.sh` (wait for DB,
  migrate with an advisory lock / `--check` guard, then exec gunicorn with sane workers/timeouts).
- [x] **P4.7 docker-compose.prod.yml:** services `web` (gunicorn), `db` (postgres:16-alpine,
  volume, healthcheck), `caddy` (automatic HTTPS, reverse proxy, serves `/static/` via web and
  `/media/public/` from a volume, sets security headers, gzip/zstd), `cron` (same image, supercronic
  with a `crontab` for: reminders 08:00, digest 18:00, clearsessions daily, axes reset, pg_dump backup
  nightly with 14-day rotation into a `backups` volume). Plus `docker-compose.yml` for local dev
  (web + db, runserver, bind mount). **Done when:** `docker compose -f docker-compose.prod.yml up`
  works locally with `DOMAIN=localhost` (Caddy internal TLS), the smoke checklist in P7.5 passes
  against it, and `check --deploy` inside the container is clean.
- [x] **P4.8 Management commands for ops:** `createadmin` (non-interactive from env, creates the User
  + AdminProfile; no admin currently exists without the Django shell), `check_email` (sends a
  test mail), `backup_media` (tar of media + private).
- [x] **P4.9 Django admin:** move to `ADMIN_URL` env (default `gestion-interne/`); register models
  with useful list_display/search/filters; read-only for audit-ish models.

### P5 — Design system foundation (the UI revamp starts here; read §6 first)

- [x] **P5.1 Page inventory.** Generate `docs/ui-inventory.md`: every URL name → view → template →
  role → purpose → key data/actions (from code, not guesses). This drives P6 ordering and prevents
  missed pages. Also note which templates are orphaned (not rendered by any view) → delete them.
- [x] **P5.2 Screenshot harness.** `scripts/screens.py` (Playwright, Chromium): starts from seeded
  DB, logs in per role, captures every inventory page at 1440×900 and 390×844, light + dark, into
  `screens/<phase>/<role>/<name>__<width>__<theme>.png`; `make screens` (flags: `--only name`,
  `--role`). Also runs axe-core (vendored into `scripts/vendor/axe.min.js`) and writes
  `screens/a11y.json` with violations per page. Capture a **"before"** set now into
  `screens/before/` (gitignored, kept locally for comparison).
- [x] **P5.3 Fonts & icons.** Download and vendor the woff2 files (Latin + Latin-ext subsets) for the chosen
  families (§6.2) with OFL licenses into `static/fonts/`; build the Lucide sprite for only the icons
  used (script `scripts/build_icons.py` with a list in `static/icons/icons.txt`); `{% icon %}` tag with
  `aria-hidden` by default and a label option.
- [x] **P5.4 CSS architecture:** `static/css/app.css` imports in order (plain CSS `@import`
  is fine with WhiteNoise, or concatenate through a tiny script if the request count matters; decide and record in §8):
  `tokens.css` (§6.3), `reset.css`, `base.css` (typography, links, focus), `layout.css` (shell,
  grid, stack/cluster utilities, container), `components/*.css` (one file per component in §6.5),
  `pages/*.css` (only when truly page-specific; aim for near zero).
- [x] **P5.5 Components (templates + CSS)** per §6.5, each with a demo on a dev-only
  `/_styleguide/` page (DEBUG only) showing every state in both themes. Screenshot it and review.
- [x] **P5.6 Layouts:** `layouts/base.html` (html/head, theme bootstrap without FOUC through a tiny
  external script, skip link, messages → toasts), `layouts/app.html` (sidebar nav on desktop,
  bottom-sheet/drawer nav on mobile, top bar with search, notifications, user menu; role-aware
  nav definitions in Python `core/navigation.py`, not duplicated across 4 base templates),
  `layouts/public.html`, `layouts/auth.html` (login/signup/reset), `layouts/print.html` (for
  printable project/evaluation sheets).
- [x] **P5.7 Theme:** light/dark/auto driven by `data-theme` on `<html>`; the preference is saved to
  UserPreferences for students AND teachers/admins (UserPreferences is per-User already), and to
  localStorage for anonymous visitors. Delete the old theme-toggle.js/themes.css.
- [x] **P5.8 HTMX setup:** vendored htmx, `django-htmx` middleware, CSRF header config in a static
  JS file, partial-template convention (`templates/<app>/partials/…`), a toast system from the
  `HX-Trigger` header.

### P6 — Page-by-page revamp (one task per area; each: rebuild on the new layout/components,
delete old CSS/inline styles/CDN links for those templates, update the smoke test if needed,
screenshots at both widths and themes reviewed, axe: zero serious/critical)

- [x] **P6.1 Auth:** login, signup choice, student/teacher signup, pending-confirmation page,
  password reset (4 pages), password change. Keep them short and trustworthy; no marketing on the forms.
- [x] **P6.2 Public site:** homepage (honest product page for ENSA, a real showcase preview, no
  fake stats/testimonials), showcase list (filters as a sidebar/sheet, cards with real covers or
  a typographic fallback, not stock gradients), public project detail (readable article-like layout,
  team, links, allowed files, likes/comments with HTMX, report dialog), report page → dialog,
  features/about merged into a single "À propos" page unless inventory shows otherwise.
- [x] **P6.3 Student core:** dashboard ("what needs my attention": deadlines, invitations, revision
  requests, then my projects as a compact table/list with status chips), project create/edit form
  (clean sections, inline validation), project detail (header with status + primary action; tabs or
  sections: Aperçu / Livrables / Jalons / Équipe / Discussion / Activité; evaluation card),
  submit confirmation (checklist that is actually computed), delete confirm.
- [x] **P6.4 Student collaboration:** invitations (received/sent), invite flow (HTMX typeahead
  over allowed students; replaces select2), teammates board, notifications page (grouped by day,
  mark-read via HTMX), calendar (month grid + agenda list on mobile, .ics link).
- [x] **P6.5 Student assignments & modules:** assignments list (grouped by urgency), assignment
  detail, option selection (compare options side by side, clear availability), create-project-from-
  assignment, my modules, join module.
- [x] **P6.6 Student profile & settings:** profile view/edit (avatar upload with preview),
  settings tabs (compte, notifications incl. digest, apparence), make public / make private flows.
- [x] **P6.7 Teacher core:** dashboard (review queue first: submitted projects awaiting action,
  upcoming deadlines, module list), modules list/detail (roster, announcements composer, exports),
  module projects, student projects list (filterable table).
- [x] **P6.8 Teacher review & grading:** project review page (deliverables with versions and
  per-file feedback threads, milestones, activity, actions: valider / demander une révision /
  rejeter with reason), grading page (rubric rows editable with HTMX add/remove, live total, mention
  preview), printable evaluation sheet.
- [x] **P6.9 Teacher assignments:** dashboard, create/edit (a multi-step feel but a single page;
  team settings reveal conditionally), options management, students selection (the page built in
  P2.1), teams view, progress (table with bulk-select action bar, filters, export), publish
  confirm, option delete confirm, module creation, my modules.
- [x] **P6.10 Admin:** dashboard (useful numbers + pending work queues: registrations, reports),
  users list (tabs, search, activate/deactivate), imports (students/teachers, with a result
  report), pending registrations, modules list/create/edit/detail/delete, teacher-module
  assignments, projects list/detail, moderation queue, exports page, statistics.
- [x] **P6.11 Search:** global search page + top-bar quick search (HTMX dropdown, keyboard nav).
- [x] **P6.12 Emails:** HTML + text templates (invitation, approval, reset, reminders, digest,
  announcement, grade) with an inline-CSS-safe simple layout; preview route in DEBUG.
- [x] **P6.13 Cleanup sweep:** delete every old per-app CSS/JS file and unused template; grep
  that no template has `<style`, `style="` (except rare dynamic widths through CSS vars),
  `onclick=`, `cdnjs`, `jsdelivr`, `fonts.googleapis`, `fa-` classes. Record the counts in the log.

### P7 — Hardening, QA, docs

- [x] **P7.1 Test gap fill:** coverage ≥ 80% on the core apps; add tests for every permission
  boundary (a matrix test: role × view → expected status), file download permissions, imports
  with malformed files, reminders/digest commands, state machine.
- [x] **P7.2 Security review pass:** run the `security-review` mindset over the whole diff
  (IDOR on every `<int:…_id>` URL, mass assignment in forms, open redirects on `next`, upload
  handling, email header injection, XSS in `|safe`/`mark_safe` uses (grep), CSV/Excel formula
  injection in exports → prefix `= + - @` cells with `'`). Fix what's found; add tests.
- [ ] **P7.3 Enforce CSP** (flip report-only → enforce); verify with screens + console-error capture in
  the Playwright harness (fail on any CSP violation or JS error).
- [ ] **P7.4 Performance pass:** query-budget tests green; Lighthouse-style checks through Playwright
  (page weight < 300 KB for app pages excluding user images, no layout shift from fonts via
  `font-display: swap` + metric fallbacks); DB indexes verified with EXPLAIN on Postgres
  for the heaviest lists.
- [ ] **P7.5 Full E2E happy paths** (Playwright scripts in `e2e/`, run through `make e2e` against
  runserver + seeded DB): signup→admin approval→login; teacher creates choice-based team
  assignment→publishes→student A picks option→invites B, C→they accept→upload deliverable v1, v2→
  submit→teacher requests revision→resubmit→grade+validate→student makes it public→anon views,
  likes require login, reports→admin hides. Also direct individual assignment and deadline reminder
  command output. All green, including against the prod compose stack.
- [ ] **P7.6 Docs:** `README.md` (what it is, screenshots from `screens/after/`, local dev quick
  start), `docs/DEPLOY.md` (VPS + Docker Compose + Caddy step-by-step: DNS, env file, first
  deploy, `createadmin`, email setup, backups/restore drill, upgrades, rollback),
  `docs/OPERATIONS.md` (cron jobs, logs, common tasks, how to rotate secrets), `CHANGELOG.md`.
  CLAUDE.md final update. Mark ROADMAP.md as superseded.
- [ ] **P7.7 Release candidate:** tag `v2.0.0-rc1` locally; write a short summary for the user of
  what changed and exactly what they need to do (§7) — in plain language, ≤ 15 lines.

### P8 — Deployment (blocked on the user; do only after P7)

- [!] **P8.1** The user picks hosting and gives access (see §7). Default recommendation to present:
  a small VPS (2 vCPU / 4 GB, e.g. Hetzner CX22 or similar) + a domain; alternative: a PaaS.
- [!] **P8.2** Push the `revamp` branch, open a PR to `main`, CI green, merge.
- [!] **P8.3** First deploy following DEPLOY.md, `createadmin`, real SMTP test, backup + restore drill,
  smoke checklist on the live URL, then hand over credentials and a 10-line usage note.

---

## 6. DESIGN SYSTEM ("Atelier") — binding for P5/P6

### 6.1 Direction
An academic, editorial, calm tool: think a well-set university report crossed with a modern
issue tracker. Dense where teachers/admins work (tables, queues), spacious and readable on
public pages. The UI must look like a product designed by a person for ENSA, not a template.

**Anti-slop rules (check every page against these before ticking a P6 task):**
1. No gradients (backgrounds, buttons, text), no glassmorphism/blur, no neon glows, no colored drop shadows.
2. No emoji in UI chrome, headings, buttons, or flash messages (remove existing "🎉", "📢", "✅", "❌").
3. One accent color. Status colors only for status. Never rainbow stat cards.
4. No "hero stat cards" row of 4 big numbers with icons as the default dashboard pattern. Numbers
   appear where they help a decision, inline or in a compact summary strip.
5. No icon in every heading/label. Icons only for recognizable actions/navigation (≤ 1 per control).
6. Left-aligned, grid-based layouts; centered text only for empty states and auth cards.
7. Real, specific French copy. No filler ("Bienvenue dans votre espace innovant !"), no
   fake testimonials/stats, no lorem. Empty states say what to do next, with one action.
8. Consistent components only (§6.5); no one-off buttons or badges invented per page.
9. Border radius 6px (controls), 10px (cards/dialogs); 1px hairline borders; shadows only for
   overlays (menus, dialogs, toasts).
10. Motion: ≤ 150ms opacity/transform, respects `prefers-reduced-motion`. No bouncing, no parallax.

### 6.2 Typography (self-hosted, OFL)
- UI & body: **Public Sans** (variable; 400/500/600). Headings on public pages and page titles:
  **Newsreader** (variable serif; 500/600, optical sizing). Numbers, IDs, dates in tables, code:
  **JetBrains Mono** (400/500), with tabular-nums in the other fonts where supported.
- Scale (rem, 16px base): 0.75 / 0.8125 / 0.875 (default UI) / 1 / 1.125 / 1.375 / 1.75 / 2.25 / 3.
  Line-height 1.5 body, 1.25 headings. Max prose width 68ch.

### 6.3 Tokens (CSS custom properties; dark values in `[data-theme="dark"]`)
```
--paper:   #F6F4EF / dark #121210     app background
--surface: #FFFFFF / dark #1A1A18     cards, tables, inputs
--sunken:  #EFECE5 / dark #0D0D0C     wells, table header, code
--ink:     #1B1A17 / dark #ECE9E1     primary text
--ink-2:   #57534A / dark #A8A396     secondary text
--ink-3:   #8A857A / dark #77736A     placeholder/disabled
--line:    #E2DED4 / dark #2C2B27     borders
--line-strong: #CFC9BC / dark #3A3934
--accent:  #1F5C57 / dark #6CB8AE     primary actions, links, focus  (deep teal)
--accent-ink: #FFFFFF / dark #0B1F1D
--accent-soft: #E3EFED / dark #16302D
--focus:   0 0 0 3px color-mix(in oklab, var(--accent) 35%, transparent)
status (fg / soft bg):
--ok #2E6B3A / #E4F0E3   dark #7DC48A / #15291A     validé
--warn #8A5A00 / #F6ECD6 dark #E0B458 / #2E2412     soumis / échéance proche
--danger #A8321E / #F7E4DF dark #F08A74 / #331A15   rejeté / en retard
--info #2B4F7A / #E2EAF3 dark #8DB1DA / #172433     en cours
--revision #6B4E9A / #ECE6F4 dark #B9A2E0 / #231C30 révision demandée
spacing: 4px scale --s-1..--s-12 (4,8,12,16,20,24,32,40,48,64,80,96)
radius: --r-sm 4px, --r 6px, --r-lg 10px, --r-full 999px
shadow (overlays only): --shadow-pop 0 8px 24px rgb(0 0 0 / .12), dark .5
```
Verify every text/background pair against WCAG AA (4.5:1 body, 3:1 large/UI) with a small
script (`scripts/contrast_check.py`) before finalizing P5.4; adjust values if needed and record the change.

### 6.4 Layout
- App shell: 248px left sidebar (collapsible to icons ≥1024px; off-canvas drawer below), top bar 56px
  (page title/breadcrumb, global search, notifications bell with count, user menu). Content max
  width 1200px for forms/detail, full width for tables. Page header component: title (+ status
  chip), meta line, primary action on the right, secondary actions in an overflow menu.
- Breakpoints: 640 / 1024 / 1280. Mobile-first CSS. Tables become stacked rows < 640px
  (labels through `data-label`).

### 6.5 Components (each: template partial + CSS + styleguide entry + all states)
button (primary/secondary/ghost/danger; sm/md; loading; icon-only with label), link, input,
textarea, select (native, styled), checkbox/radio/switch, file input with drop area + selected
file preview, form field wrapper (label, help, error, required marker), fieldset/section,
status chip (5 project statuses + assignment statuses), badge/count, avatar (image or initials,
deterministic muted color from the name hash within the palette), card, table (sortable header
links, row actions, bulk-select bar, empty row), description list, tabs (links, not JS), toast
(from Django messages; auto-dismiss except errors), alert/callout, dialog (native `<dialog>` for
confirmations; replaces confirm pages where it's safe, but keep no-JS fallback pages for destructive
actions), dropdown menu, pagination, empty state, skeleton/loading (htmx-indicator), progress
bar (team/assignment completion), timeline (activity feed), comment thread, file row (name,
version badge, size, date, download, history disclosure), deadline pill (relative "dans 3 jours" +
absolute on hover, colored by urgency), stepper (assignment creation), stat strip, calendar grid,
search result list, breadcrumb, filter bar.

### 6.6 Accessibility (non-negotiable)
Semantic landmarks, one `h1` per page, visible focus everywhere, labels on all inputs, errors
linked through `aria-describedby`, color never the only signal (chips have text), keyboard-operable
menus/dialogs/typeahead, `lang="fr"`, target size ≥ 24px, respects reduced motion. axe: zero
serious/critical on every page before a P6 task is ticked.

---

## 7. NEEDS-USER (ask only these, and only when reached; batch them in one message)

1. **Push permission:** OK to push branch `revamp` to `github.com/walideddouaicer/DevWebProject`
   and open a PR? (Needed for CI and P8. Ask at the end of P7.)
2. **Hosting choice + access** (P8): a VPS with SSH access, or a PaaS account; a domain name (or use the
   host's subdomain).
3. **SMTP credentials** for real email (e.g. a Gmail app password, Brevo, Mailgun), plus the sender address.
4. **First admin** username and email (a password is generated and shown once).
5. (Optional) A Sentry DSN.

Everything else in this plan is decided by Claude.

---

## 8. DECISIONS (append; newest last)

- **D1 (2026-09-30)** Keep Django + server-rendered templates; add HTMX for interactivity. No SPA:
  the app is forms, lists, and workflows; an SPA would double the surface area for no user benefit.
- **D2** Hand-written CSS design system without Tailwind: no Node/build step in production,
  full control over a distinctive look, easy CSP.
- **D3** Docker target is Python 3.13 (mature wheels); the code must also run on 3.14 locally.
- **D4** Deployment reference: a single VPS with Docker Compose (web, Postgres, Caddy, cron). It's the cheapest
  and simplest to operate for a school-scale app, with automatic HTTPS through Caddy.
- **D5** Deliverables are private files downloaded through permission-checked views (FileResponse).
  That's fine at school scale; revisit X-Accel/S3 only if needed.
- **D6** Project workflow logic lives in model methods (state machine), matching the existing fat-model convention.
- **D7** Work happens on branch `revamp`; `main` stays as the pre-revamp reference until the P8 merge.
- **D8** Design direction "Atelier" (§6): editorial/academic, teal accent, Public Sans + Newsreader
  + JetBrains Mono, strict anti-slop rules.
- **D9** UI language stays French only; no gettext extraction (the effort is not worth it for a single-language
  audience). Code stays English.
- **D10** Keep the Django test runner (no pytest migration) to limit churn; add coverage.py.
- **D11** Keep the existing migrations (no squash) even though no production data exists, to keep history honest.

---

## 9. LOG (append; newest last)

- **2026-09-30** · plan · Full review done (17 bugs reproduced at runtime, see §3). PLAN.md written,
  branch `revamp` created. Next: P0.1.
- **2026-09-30** · P0.1–P0.9 · Scaffold removed; requirements split + pinned (Django 5.2.17,
  reportlab 5, pillow 12 — all fine); ruff formatted the codebase; Makefile; `seed_demo`
  (35 users, 18 projects); smoke test (KNOWN_FAILURES pinned with bug ids); 24 regression
  tests verified to fail for the right reason; CI yml; suite green on Postgres too.
  Notes: smoke test uses kwarg overrides for ambiguous route params. Media from seeding goes
  to `media/` (gitignored). Next: P1.1.
- **2026-09-30** · P1.1–P1.9 · Permission layer (`accounts/permissions.py`); B1 fixed via
  member helper; Project workflow state machine (submit/validate/reject/request_revision/
  reopen) + 13 tests; legacy status/approve/reject/feedback endpoints deleted; ProjectForm
  lost its collaborators field; all mutating views POST-only (smoke test now has zero
  "mutates" exceptions); private deliverable storage + permission-checked downloads +
  public opt-in (`Project.public_deliverables`); student assignment views role-guarded;
  django-axes lockout (disabled under `manage.py test`, re-enabled per test); public logout
  was a GET link (405 on Django 5) → form. **Found B25** (stored XSS via inline JS handlers),
  patched; full removal in P6. Next: P2.1.
- **2026-09-30** · D12 (P2.1 triage) · Built: admin statistics, teacher assignment students +
  teams (plain placeholder templates, redesigned in P6). Redirected: admin users/, users/
  students/, users/teachers/ → users_list tabs; public /explore/ → showcase. Deleted unrouted
  admin views module_oversight, toggle_module_status, recent_module_activity, and the duplicated
  registration URL entries. Smoke KNOWN_FAILURES is now empty.
- **2026-09-30** · P2.2–P2.11 · B9 (NULL ids + data migrations), B10 (progress recursion),
  B11 (completion by students), B12/B13 (draft silence, sync at publish, late enrollees via
  `ModuleEnrollment.attach_published_assignments`), B18 (`manageable_assignments`: co-teachers),
  B16/B17 (SITE_URL + `ensa_project_manager/emails.py` + `templates/emails/*.txt`; signup
  password validators), B22 (password reset + change for all roles), B23/B24 (F() counters,
  `public_projects()` helper), DB constraints + indexes (verified on Postgres), dead code:
  6 unregistered context processors, debug prints, paste-instruction comments, error handlers
  that showed `str(e)` to users now log + show a generic message (admin import row errors
  intentionally still detailed). ValidationError shown via `.messages` (no more "['…']").
  Next: P3.1.
- **2026-09-30** · D13 (P3.4) · Badges are NOT cached: one `accounts.context_processors.badges`
  with ≤4 indexed COUNTs per request beats cache invalidation complexity; exact at all times.
  Removed the 3 per-app processors, `clear_student_context_cache`, and the dead
  `pending_module_approvals` banner.
- **2026-09-30** · P3.1–P3.5 · Views split into packages (splitter script: copies all imports,
  relocates relative imports, re-exports in `views/__init__`; ruff prunes). Forms for all
  free-text POSTs; admin module create/edit had NO validation before (AdminModuleForm). Query
  budgets + growth tests (tests/test_query_budget.py) → fixed N+1s on admin users/projects/
  modules/dashboard, teacher dashboard/projects/module projects. One uncached badges processor.
  Pagination helper/component on 6 lists. Next: P4.1.
- **2026-09-30** · D15 (P4.6) · No supercronic: `manage.py run_scheduler` (JSON state file,
  once per local day, catch-up after downtime, never repeats — the digest isn't idempotent).
  Backups (P4.7) will run in a separate postgres:16-alpine service so pg_dump matches the
  server version and the app image needs no apt packages. Gunicorn 26 needs
  `--control-socket /tmp/gunicorn.ctl` (default path not writable for the non-root user).
- **2026-09-30** · P4.1–P4.9 · Env-driven prod settings with guard rails (tests spawn a fresh
  interpreter), WhiteNoise, CSP report-only, error pages, /healthz middleware (first in chain),
  robots/security.txt, Sentry opt-in, Docker image (350 MB, non-root, healthy), prod compose
  (web/scheduler/db/caddy/backup) verified end-to-end locally over HTTPS, dev compose,
  createadmin/check_email, Django admin at ADMIN_URL, single `PendingRegistration.approve`.
  Useful commands for later: `docker compose -f docker-compose.prod.yml -p ensa-local up -d
  --build` with a throwaway .env (DOMAIN=localhost, HTTP_PORT=8080, HTTPS_PORT=8443,
  DJANGO_CSRF_TRUSTED_ORIGINS=https://localhost:8443); tear down with `down -v`; delete .env.
  Next: P5.1 (UI inventory), then the design system.
- **2026-09-30** · P5.2 · `scripts/screens.py` (Playwright + axe; seeds its own throwaway DB and
  server on :8765). Baseline `screens/before/`: 420 shots, 105 pages, 93 with serious/critical
  a11y issues (color-contrast 91, button-name 19, scrollable-region-focusable 12, select-name
  10, label 9). Found B26. Chromium headless installed in ~/.cache/ms-playwright.
- **2026-09-30** · D16 (P5.4) · CSS sources in `static/css/src/NN-*.css` (+ `components/`),
  concatenated by `scripts/build_css.py` into committed `static/css/app.css` (one request, no
  @import waterfall, no Node). Tests fail if app.css is stale, if tokens fail WCAG (contrast
  script), or if the two dark-token blocks diverge. Token tweaks vs §6.3: --warn #7A5000,
  --ink-3 #75706A / dark #8C877C, new --border-input (#8C867A / #6E6A60, 3:1 for fields).
  Workflow: edit src → `python scripts/build_css.py` → commit both.
- **2026-09-30** · P5.3–P5.8 · Fonts + Lucide sprite (`{% icon %}`), CSS build (D16), tokens
  WCAG-verified, ~30 components, tags (status_chip, avatar, deadline, field), layouts
  (`layouts/base|app|public|auth.html`), `ui/navigation.py`, `static/js/app.js` (drawer, menus,
  toasts, `data-confirm` dialogs, bulk select, theme), theme endpoint `ui:set_theme`, HTMX 2
  vendored with CSP-safe config + `HtmxMessagesMiddleware` (messages → HX-Trigger toasts).
  **P6 conventions (read before every P6 task):**
  - Pages extend `layouts/app.html` (auth'd), `layouts/public.html` or `layouts/auth.html`;
    `{% load ui %}`; page header = `.page-header` markup (see `ui/templates/ui/styleguide_shell.html`).
  - Forms: `{% field form.x %}` per field (or custom markup using .field classes); submit
    buttons `.btn .btn-primary`; destructive forms get `data-confirm="…" data-confirm-danger`.
  - NO `style="…"`, `onclick=`, `<style>`, `<script>` inline, CDN links, emoji, `fa-*`.
    Progress = `<progress class="meter">`. Colors only via tokens/classes.
  - HTMX partials in `templates/<app>/partials/`; views check `request.htmx`.
  - Visual check: `/_styleguide/` for components; `scripts/screens.py --only <name> --role <r>`
    for pages (seeds its own DB). For a quick signed-in shot: run a throwaway server on :8767
    and use a small Playwright script (login form → goto → screenshot). Kill servers with
    `ps aux | grep "[r]unserver 127.0.0.1:876" | awk '{print $2}' | xargs -r kill` (never
    `pkill -f` with the pattern in the same command line: it kills its own shell).
  - Delete the old per-page CSS/JS and `<style>` blocks of each template you rebuild.
- **2026-09-30** · P6.1 · Auth pages rebuilt on layouts/auth (login with `next`, signup choice,
  signup form, reset ×4, lockout) and password change on layouts/app (shared by all roles;
  student-specific copies deleted). Accounts without a role get home=public homepage. axe: 0.
- **2026-09-30** · P6.2 · Public site rebuilt (homepage, À propos (features → 301), showcase,
  article-style project page, report form), `components/project_card.html` with typographic
  cover fallback (`|tone` filter), like/comment work without JS and via HTMX partials
  (`public/partials/`), JSON kept for scripts. All public views use `public_projects()`.
  Deleted public/static and base_public/features templates. axe: 0 serious on 9 pages.
- **2026-09-30** · P6.3 · Student dashboard (B26 fixed), project detail (sections + aside),
  create/edit form, upload deliverable (dropzone), milestone form, submit confirmation (real
  blockers from `Project.get_submission_blockers`), delete confirm. Found + fixed: native date
  inputs were EMPTY since the French locale switch (P4.1) → `ui/widgets.py` NativeDate(Time)Input
  render ISO; remove_collaborator was GET-mutating (fixed + test + smoke scenario).
  Preview helper: `/tmp/claude-1000/preview.sh start|stop` (PID file; recreate from log if /tmp
  was wiped: seeded throwaway DB + runserver :8767) and `/tmp/claude-1000/shot_login.py URL OUT
  WIDTH THEME USER [menu]`. Known gap: feedback on older deliverable versions is only visible in
  the version history, not merged into the latest version's thread.
- **2026-09-30** · P6.4 · Invitations, notifications (day groups, unread marker, mark-read),
  teammates board, calendar (grid + agenda, mobile agenda only), invite picker: select when ≤30
  candidates else HTMX search (`student:invite_candidates`, full-page fallback without JS).
  `Project.invite_candidates()` model method — fixed a NOT IN (NULL) bug that emptied the list
  whenever another team of the assignment had no collaborators.
- **2026-09-30** · P6.5 · Student assignments list grouped by next action (view builds
  `groups`), assignment detail, subject choice (radio cards, one template for both entry points),
  start-project form, my modules (join + leave with confirm). Model choice labels translated to
  French (migrations *_french_choice_labels). join_module now returns to Mes modules.
- **2026-09-30** · P6.6 · Student settings tabs (profil / notifications via
  `NotificationPreferencesForm` incl. assignment_reminders + digest / apparence / compte),
  profile view + edit, publish-to-showcase form (single form, tags, public files opt-in),
  unpublish confirm. `AccountSettingsForm` deleted. delete_profile_picture POST-only.
- **2026-09-30** · P6.7 · Teacher dashboard (review queue, deadlines with hand-in %, modules),
  modules list, module detail (assignments, recent projects, roster, announcement composer with
  confirm, Excel roster), shared `teacher/_projects_table.html` for projects lists.
  module_management → redirect to module detail (template deleted). Fixed: dashboard student
  count was multiplied by projects (missing distinct) + test; year labels French. Global rule:
  `.content > * + *` spacing.
- **2026-09-30** · P6.8 · Teacher project review (decision panel: validate / revision with
  required message / reject with optional reason, per-file feedback threads, milestones,
  discussion, activity) and grading (editable rubric rows via `data-add-row`/`data-remove-row`
  + `<template>`, live criteria mean, print button + `90-print.css`). Verified with Playwright:
  add-row and mean work, no JS errors.
- **2026-09-30** · P6.9 · Teacher assignments: dashboard (drafts/open/closed + module tabs),
  detail (overview, hand-in %, subjects, next step), create/edit sharing `_form_fields.html`
  with `data-show-if` conditional fields (app.js; supports `!field`), subjects management,
  students selection (select-all + live count), teams, progress with bulk bar, publish
  checklist, subject delete, module creation. assignments_dashboard/detail views rewritten
  (−230 lines). my_modules → redirect. Create of a direct "specific students" assignment now
  lands on the students page. Old teacher base/CSS/JS deleted.
- **2026-09-30** · P6.10 · Admin area on `layouts/app.html`: dashboard (attention cards for
  registrations/reports, stat strip, latest projects, top modules), users list (tabs, filters,
  toggle active with confirm), pending registrations, student/teacher imports (dropzone +
  result report), modules list/create/edit (shared `_module_fields.html`)/detail/archive,
  teacher-module assignments (workload now one annotated query), projects list (filters,
  export keeps filters) and detail, moderation queue (hide/unhide/dismiss with note), exports,
  statistics. remove_student_from_module POST-only (JSON only for XHR). Fixed `.card-link`
  overriding `.stack` display. Deleted old admin base + CSS and legacy student base.css/main.js.
  Screens: 16 admin pages, 0 serious a11y. Note for P6.13: filter bars stack tall on 390px.
- **2026-09-30** · P6.11 · Search moved to `search/services.py` (`search(user, q, limit)` →
  role + `Section`/`Result` dataclasses, `reverse()` URLs, ≥2 chars, member projects also
  match module code/name, teacher people search prefetches enrollments — no N+1). Full page
  on app/public layout by role; top-bar HTMX quick search (`search:quick`, 4 per section,
  "/" shortcut, arrows, Escape closes, click-outside). `|highlight:q` filter (escapes, then
  `<mark>`). Fixed globally: `.col-actions` width 1% pushed stacked-table buttons off-card on
  mobile. screens.py skips HTMX fragments and audits search for every role with `?q=web`.
  `search.SearchQuery` model is unused (left in place; drop in P7 cleanup with a migration).
- **2026-09-30** · P6.12 · Emails are multipart: `emails/<name>.txt` + `<name>.html` extending
  `emails/base.html` (table layout, inline styles — the only place inline styles are allowed;
  P6.13 grep must exclude `templates/emails/`). New: `project_update`, `deadline_reminder`,
  `digest`; HTML for registration received/approved, invitation, announcement, password reset.
  `wants_email(user, flag)` centralises preferences (inactive/no email/opted out/digest → no).
  `Project.notify_team(..., email="Heading", details=...)` bulk-creates notifications and emails
  on commit; used by validate / reject (reason) / request_revision (message) and grading
  (`validate(notify=False)` + one combined "noté et validé" message — was two before).
  Digest and reminder commands now use templates (+ select_related, no N+1). DEBUG-only
  `/_emails/` previews (`email_previews.samples()` also feeds tests/test_emails.py).
  Removed emoji from announcement notifications. Left for P6.13: emoji in a few
  `messages.success` strings (student/views/projects.py, teacher/views/modules.py).
  Known wart: reminder notifications end with a "(J-3)" dedupe marker visible to users.
- **2026-09-30** · P6.13 · Sweep (templates excl. `templates/emails/`): `<style` 0, `style="` 0,
  inline `on*=` handlers 0, `cdnjs`/`jsdelivr`/`fonts.googleapis` 0, `fa-` 0, inline `<script>` 0.
  Styleguide's 5 inline styles + `onsubmit` → classes (`components/30-styleguide.css`,
  `.grid-wide`). Deleted orphan `static/css/main.css`, `teacher/static/`. No unreferenced
  templates. Emoji removed from Python messages. Hardcoded paths → `reverse()`/`reverse_lazy`
  (admin redirects, toggle-user redirect, calendar event URLs, password-change success).
  **Bug fixed:** build_css sorted by relative path, so `90-print.css` came before
  `components/*` and lost the cascade (`.app` stayed grid in print) — now sorted by file name;
  verified in Chromium print emulation. Kept on purpose: `static/css/errors.css` (standalone
  error pages), `ui/navigation.py` path prefixes (active-link matching).
- **2026-09-30** · P7.1 (part 1) · `test_permission_matrix` in tests/test_smoke.py reuses the
  crawl (cached per class): anon → login redirect, wrong role → 403, outsider student /
  outsider teacher never get 200 on someone else's project/module/assignment. Found ~125
  inconsistencies (404s / redirects instead of 403, no leaks): 45 student+teacher views moved
  from `login_required` + manual profile lookup to `@student_required` / `@teacher_required`
  (`request.student` / `request.teacher`); `get_student_or_error` / `get_teacher_or_error`
  deleted. Duplicate `student:password_change(_done)` routes removed (settings links to the
  global one). Allowlisted: 3 legacy admin RedirectView aliases; `student:deliverable_download`
  (shared by design; private files stay 404 for anon so ids can't be probed).
- **2026-09-30** · P7.1 (part 2) · Coverage 79% → 83%. Team rules consolidated on the model:
  `Project.check_can_join(student)` (shared by `add_assignment_collaborator` and the new
  `Project.invite(by, recipient)`), `CollaborationInvitation.accept()/decline()` (accept
  re-checks the rules, closes the invitation if they fail, notifies the team);
  `add_collaborator` (POST-only now) and `respond_to_invitation` views went from ~250 lines to
  ~40. Signup views merged into `_signup()`; username/email duplicate checks case-insensitive,
  email stored lowercase; dead `accounts:admin_signup` stub removed (admins: `createadmin`).
  New suites: tests/test_team_flows.py, tests/test_accounts_modules_admin.py (validators,
  signup, join/leave module, admin assign/unassign/unenroll, moderation), corrupt-import test.
  Remaining < 80%: teacher/views/assignments.py 66%, student/views/projects.py 67% — covered
  end-to-end by P7.5 instead.
- **2026-09-30** · P7.2 · Review: no `|safe`/autoescape-off in HTML templates; one
  `mark_safe` (`|highlight`, escapes first); no raw SQL (health check only); no redirects to
  user input; ModelForm field lists narrow (no status/owner/visibility fields; ProjectForm
  module limited to enrolled, removed on assignment projects); URLFields reject `javascript:`;
  uploads allowlisted + PIL-verified, deliverables private. New
  `test_outsiders_cannot_mutate_by_post` (smoke): unrelated student / teacher POST a rich
  payload to every id-taking route → no DB change, fingerprint widened (comments, likes,
  reports, grades, announcements, titles, modules, options); public like/comment/report on a
  private project must 404. Fixed: spreadsheet formula injection (`exports.safe_cell` on
  every exported cell), export filename via `content_disposition_header`, email subjects
  collapsed to one line, `.ics` escaping of `\r`. Export header colour → accent.
  tests/test_security.py covers these + login `next` open-redirect.
