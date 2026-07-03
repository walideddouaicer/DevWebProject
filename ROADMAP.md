# ROADMAP — ENSA Project Manager

Feature backlog agreed on 2026-07-03. Work through it top-to-bottom (ordered by
impact vs effort and dependencies). Check items off as they land; add notes/dates
next to completed items. This file is the single source of truth for what's next —
keep it updated every session.

## Phase 1 — Quick wins that close broken loops

- [x] **1. Deadline reminders** *(students)* — done 2026-07-03.
  `manage.py send_deadline_reminders` (supports `--dry-run`); schedule it daily via
  Windows Task Scheduler / cron.
  `is_deadline_approaching()` exists but nothing triggers it. Management command
  (`send_deadline_reminders`) run daily via cron/Task Scheduler: notify students at
  J-7 / J-3 / J-1 for assignment deadlines and selection deadlines (only students
  who haven't submitted). In-app `Notification` always; email only if
  `UserPreferences.assignment_reminders` and `email_notifications` allow. No duplicate
  reminders for the same threshold.

- [x] **2. Report moderation queue** *(admins)* — done 2026-07-03.
  `/administrator/moderation/reports/` with hide/unhide/dismiss + owner notifications;
  linked from the admin dashboard quick actions.
  Users can report projects and `is_reported` auto-flags at 3 reports, but there is
  NO admin UI to review them (only raw Django admin). Page listing reported projects
  with their reports; actions: hide project (`is_hidden_by_admin`), unhide, dismiss
  reports (mark `is_reviewed` + reset flags), admin notes. The nav badge
  (`reported_projects_count`) already counts these.

- [x] **3. File-upload validation** *(all)* — done 2026-07-03.
  `student/validators.py` (extension allowlists + size limits), wired into
  deliverables, profile pictures, and cover images.
  Deliverables only check size (10MB), not type. Extension allowlist
  (docs/archives/images/code), shared validator, applied to `DeliverableForm` and
  image uploads (profile picture, cover image).

## Phase 2 — Core academic workflow

- [x] **4. Grading / evaluation model** *(teachers, students)* — done 2026-07-03.
  `ProjectEvaluation` (score /20 + mention + appréciation) + `EvaluationCriterion`
  rubric rows. Teacher grades at `/teacher/projects/<id>/grade/` (linked from the
  review page, can validate at the same time); students see the grade card on their
  project page; whole team notified. Registered in Django admin. 7 tests added.

- [x] **5. Bulk actions on submissions** *(teachers)* — done 2026-07-03.
  Checkbox selection + action bar on the assignment progress page: validate or
  request revision (with shared comment) for many projects at once, with team
  notifications and direct-assignment sync. 5 tests added.

- [x] **6. Real search** *(all)* — done 2026-07-03.
  Role-aware global search at `/search/` (grouped results: projects, vitrine
  publique, modules, personnes). Anonymous → public projects only; students → own
  projects + enrolled modules + showcase; teachers → their modules' projects &
  enrolled students; admins → everything. Nav links added for students & teachers.
  7 scoping tests (incl. no-leak assertions).

- [x] **7. Excel/PDF exports** *(teachers, admins)* — done 2026-07-03.
  Admin: projects .xlsx (honours list filters), users .xlsx (2 sheets), statistics
  PDF report + real exports page (was a missing template → 500). Teacher: module
  roster .xlsx (module page button) and assignment results .xlsx incl. grades &
  mentions (progress page button, replaced the fake client-side export). Shared
  builders in `administrator/exports.py`. 10 tests added.

## Phase 3 — Collaboration & visibility

- [ ] **8. Calendar view + .ics export** *(students)*
  One calendar of assignment deadlines, selection deadlines, milestones, and project
  end dates. `.ics` feed/download so students can subscribe from Google Calendar.

- [ ] **9. Find teammates board** *(students)*
  For team assignments: students without a team can flag themselves "available",
  visible to classmates in the same module/assignment (teachers already see
  `unassigned_students`; students can't).

- [ ] **10. Module announcements** *(teachers)*
  One message broadcast to all enrolled students of a module → in-app notification
  (+ optional email). Notification infrastructure already exists.

- [ ] **11. Deliverable versioning** *(students, teachers)*
  Re-uploading a report currently just adds another file. Group files by deliverable
  name and show v1/v2/v3 history; review page shows latest with history expandable.

## Phase 4 — Administration & polish

- [ ] **12. Teacher bulk-import (Excel)** *(admins)*
  Mirror of the existing student import for teacher accounts.

- [ ] **13. Account deactivation UI** *(admins)*
  Disable a departed student/teacher (`user.is_active = False`) from the users list,
  with confirm + reactivate. Today only possible via Django admin.

- [ ] **14. Email digests respecting preferences** *(all)*
  Preferences are saved and honored for invitations; extend to all notification
  types, with a daily digest option (management command) instead of one email per
  event.

- [ ] **15. Test suite expansion** *(dev)*
  Only 11 tests exist. Priorities: assignment/team-size logic, registration approval
  flow, option-selection race, submission workflow, then each new feature above as
  it lands.

## Done

- [x] Pin requirements, env-based settings + security hardening, remove dead `projects` app.
- [x] Bug-fix sweep 2026-07-03 (18 fixes: broken teacher context processor fields,
  search 500s, add_feedback crash, profile picture crash, missing account_settings
  template, non-atomic registration approval, dropped showcase tags, inert
  notification preferences, dashboard stat, option race condition, admin badges,
  stale badge cache, assignment sync on validate/reject, past-deadline save freeze,
  milestone metadata, duplicate student IDs at signup, is_staff gates, STATIC_ROOT).
