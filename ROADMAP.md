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

- [ ] **4. Grading / evaluation model** *(teachers, students)*
  Validation is currently pass/fail only. Add rubric + score + per-criterion
  feedback: `Evaluation` model (project, teacher, overall score /20, comments) +
  optional `RubricCriterion` scores. Teacher grades from the review page; students
  see grade + feedback on the project page. Notify team on grading.

- [ ] **5. Bulk actions on submissions** *(teachers)*
  Validate / request-revision several projects at once from the assignment progress
  list (checkboxes + action bar) instead of opening each project.

- [ ] **6. Real search** *(all — empty `search` app)*
  Global role-aware search page: projects, modules, users. Students search their own
  scope + public projects; teachers their modules' projects/students; admins
  everything. Currently the stub views just redirect to the public showcase search.

- [ ] **7. Excel/PDF exports** *(teachers, admins)*
  openpyxl + reportlab already installed; admin export views are placeholders.
  Exports: module rosters, submission status per assignment, project lists, grades
  (after #4), user lists. Mirrors the existing student Excel *import*.

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
