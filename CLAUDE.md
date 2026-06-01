# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project

**ENSA Project Manager** — a Django 5.2 web platform for managing engineering-school
student projects. Four user roles (student, teacher, administrator, plus public
visitors) collaborate around projects, modules, and assignments.

- Python/Django 5.2, SQLite in dev (Postgres-ready via env vars).
- No frontend framework — server-rendered Django templates + per-app CSS/JS under
  each app's `static/` directory.
- Local dependency for image/PDF/Excel work: Pillow, reportlab, openpyxl, matplotlib.

## Running it

```bash
venv\Scripts\python.exe manage.py runserver     # dev server
venv\Scripts\python.exe manage.py check          # system check
venv\Scripts\python.exe manage.py check --deploy # production readiness
venv\Scripts\python.exe manage.py makemigrations
venv\Scripts\python.exe manage.py migrate
```

The virtualenv lives in `venv/` (gitignored). On this Windows machine use
`venv\Scripts\python.exe`.

## Configuration (important)

Settings are environment-driven (`ensa_project_manager/settings.py`):

- Secrets/config come from environment variables; a gitignored `.env` file is
  auto-loaded in dev by a small built-in loader (no `django-environ` dependency).
- Copy `.env.example` to `.env` to override defaults locally.
- `DEBUG` defaults to **True** for dev. When `DEBUG=False`, production security
  hardening (HTTPS redirect, HSTS, secure cookies, nosniff, X-Frame-Options)
  activates automatically — keep that block intact.
- DB defaults to SQLite; set `DB_ENGINE` + `DB_*` for Postgres.
- Email defaults to the console backend; set `EMAIL_BACKEND` + `EMAIL_*` for SMTP.

## App layout

| App             | Responsibility |
|-----------------|----------------|
| `public`        | Landing pages + public project showcase (views, likes, comments, reports) |
| `accounts`      | Registration via `PendingRegistration` → admin approval; role selection |
| `student`       | The core domain. Profiles, projects, deliverables, milestones, collaboration invitations, notifications, assignment participation, public toggling. **Largest app.** |
| `teacher`       | Modules, enrollments, project assignments (`direct` / `choice_based`), project options, review/validate |
| `administrator` | Dashboard, user/module management, moderation, pending registrations |
| `search`        | **Currently empty stubs** — search/filter not yet implemented |

After login, `ensa_project_manager/views.py:smart_redirect` routes users to the
right dashboard by checking AdminProfile → TeacherProfile → StudentProfile (in
that priority order). Role is determined by which `*Profile` row a `User` has.

## Key models (most live in `student/models.py`)

- `Project` — the central model. Carries: project type, status
  (`in_progress`/`submitted`/`validated`/`rejected`), owner + collaborators,
  optional `module` link, assignment-integration fields, public-showcase fields,
  and engagement counters. Has substantial business logic on the model itself
  (team-size validation, `calculate_progress()`, `is_on_track()`, public toggling).
- `teacher.Module` / `ModuleEnrollment` / `ModuleAssignment` — modules + who's in them.
- `teacher.ProjectAssignment` / `ProjectOption` / `DirectStudentAssignment` — the
  assignment system. `ProjectOption.select_for_team()` uses `select_for_update()`
  for atomic, race-free option claiming — preserve that pattern.
- Engagement/social: `ProjectLike`, `PublicProjectComment`, `ProjectView`,
  `ProjectReport`, `ShowcaseTag`, `Notification`, `ProjectActivity`, `UserPreferences`.

## Conventions & gotchas

- **Fat models**: domain logic lives on models, not in a service layer. Follow suit.
- **Mixed language**: UI strings and many messages are in **French**; code/identifiers
  are English. `USE_I18N=True` but there are no translation catalogs yet — match the
  surrounding language of whatever you edit.
- **View files are large** (`student/views.py` ~1400 lines; `teacher/assignment_views.py`
  ~1090). `student/views.py` does `from .assignment_views import *`.
- **No test suite yet** — every `tests.py` is an empty stub. Worth adding when touching
  assignment/team-size logic.
- **N+1 risk**: `Project.calculate_progress()` issues several queries and is also
  called by `is_on_track()`. Use `select_related`/`prefetch_related`/annotations in
  list views; be careful calling these methods in loops.
- Per-app static files; shared base styles in `static/css/main.css`.
- There's a light/dark/auto theme system (`UserPreferences.theme_preference`,
  `student/static/student/js/theme-toggle.js`).

## Git

- Branch: `main`. Commit messages end with the `Co-Authored-By` trailer.
- `db.sqlite3`, `media/`, `venv/`, `.env`, and IDE dirs are gitignored.
- The legacy `projects` app was removed; its old `projects_*` tables may still exist
  in local `db.sqlite3` but are orphaned and unused.

## Known upgrade backlog (planned with the user)

Ordered roughly by priority. Done items are checked.

- [x] Pin `requirements.txt`; env-based settings + security hardening; remove dead `projects` app.
- [ ] Build the real **search** feature (the empty `search` app).
- [ ] File-upload validation (deliverables + images): type/size limits.
- [ ] Real email notifications (backend is env-ready; wire the sends).
- [ ] Deadline reminder jobs (`ProjectAssignment.is_deadline_approaching()` exists, nothing triggers it).
- [ ] PDF/Excel exports (reportlab/openpyxl already installed).
- [ ] Grading/evaluation model (rubric + score + feedback).
- [ ] Add a test suite, starting with assignment/team-size logic.
