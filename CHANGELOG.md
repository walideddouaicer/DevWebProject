# Changelog

## 2.0.0 — unreleased (release candidate `v2.0.0-rc1`)

A production-readiness pass and a complete redesign of the interface.

### Security
- Every state change is POST-only with CSRF protection (many used to happen on GET).
- Role checks are uniform: `@student_required` / `@teacher_required` / `@admin_required`;
  teachers only see projects of the modules they teach; wrong-role requests get a 403.
  A test requests every URL as every role, and POSTs to every id-taking URL as outsiders.
- Deliverables are private files served only through a permission-checked view; upload
  allowlist without active content (HTML, SVG, JS); images are verified.
- Stored XSS through inline JavaScript handlers fixed; no inline scripts or styles remain and
  the Content Security Policy is enforced.
- Login rate limiting (django-axes), password validators on sign-up, password reset flow.
- Spreadsheet formula injection in exports neutralised; email subjects and calendar
  exports can no longer be used to inject headers or properties.
- Production settings refuse to start without a real secret key, allowed hosts and site URL;
  HSTS, secure cookies, proxy-aware HTTPS.

### Fixed
- 500 errors for team owners, missing templates, anonymous access to assignments, a second
  teacher without an id, infinite recursion in progress calculation, wrong completion
  percentages, notifications sent for draft assignments, late enrolments not receiving
  assignments, team-wide status sync, broken approval email links, counters that lost updates
  under concurrency, likes/comments on hidden projects, and more (26 logged bugs, each with a
  regression test).
- Grading no longer fails when the suggested rubric criteria are left empty, and the grading
  form keeps what the teacher typed when there is an error.

### New
- A design system ("Atelier"): tokens, components, light/dark themes, accessible by default
  (axe checks on every page), self-hosted fonts and icons, print styles for grading sheets.
- Every page rebuilt: public site and showcase, sign-up/login, student, teacher and admin
  areas.
- Search page and a top-bar quick search with keyboard navigation.
- HTML emails with a text fallback; emails for teacher decisions (validated, changes
  requested, rejected, graded); daily digest option; deadline reminders at J-7/3/1/0.
- Team building on the model: invitations re-check the rules when accepted; a
  "looking for a team" board; versioned deliverables with per-file feedback threads.
- Excel import of students/teachers with a result report; Excel/PDF exports.
- Calendar with an `.ics` feed.

### Operations
- Docker image (non-root), Docker Compose stack with PostgreSQL 16, Caddy (automatic HTTPS),
  a scheduler container for daily jobs, nightly backups; `/healthz` endpoint; `createadmin` and
  `check_email` commands; optional Sentry.
- CI on GitHub Actions against PostgreSQL; `make check`, `make e2e`, `make qa`.
- Documentation: `docs/DEPLOY.md`, `docs/OPERATIONS.md`.

### Removed
- Unused scientific dependencies, dead code and templates, the old per-page CSS/JS, the
  administrator self-sign-up stub.

## 1.x

The original application (2024), before this release.
