# Student calendar + iCalendar export (ROADMAP #8).
#
# One place to see every date that matters: assignment deadlines, selection
# deadlines, project milestones and project end dates. The .ics feed lets
# students subscribe from Google Calendar / Outlook.

import calendar as pycalendar
from datetime import date, timedelta, timezone as dt_timezone

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from django.utils import timezone

from .models import StudentProfile, Project, ProjectMilestone
from teacher.models import ProjectAssignment


def collect_student_events(student):
    """All calendar events for a student, as dicts with date/type/title/url."""
    events = []

    # Assignment deadlines from enrolled modules
    enrolled_module_ids = list(student.module_enrollments.filter(
        is_active=True
    ).values_list('module_id', flat=True))

    assignments = ProjectAssignment.objects.filter(
        module_id__in=enrolled_module_ids,
        status__in=['published', 'in_progress'],
    ).select_related('module')

    for assignment in assignments:
        if assignment.deadline:
            events.append({
                'date': timezone.localtime(assignment.deadline).date(),
                'time': timezone.localtime(assignment.deadline),
                'type': 'deadline',
                'title': f"Rendu: {assignment.title}",
                'subtitle': assignment.module.code,
                'url': f"/student/assignments/{assignment.id}/",
                'uid': f"assignment-{assignment.id}-deadline",
            })
        if assignment.assignment_type == 'choice_based' and assignment.selection_deadline:
            events.append({
                'date': timezone.localtime(assignment.selection_deadline).date(),
                'time': timezone.localtime(assignment.selection_deadline),
                'type': 'selection',
                'title': f"Sélection: {assignment.title}",
                'subtitle': assignment.module.code,
                'url': f"/student/assignments/{assignment.id}/",
                'uid': f"assignment-{assignment.id}-selection",
            })

    # Projects (own + collaborated): milestones and end dates
    projects = Project.objects.filter(
        Q(student=student) | Q(collaborators=student)
    ).distinct()

    for project in projects:
        if project.end_date:
            events.append({
                'date': project.end_date,
                'time': None,
                'type': 'project_end',
                'title': f"Fin du projet: {project.title}",
                'subtitle': project.module.code if project.module else '',
                'url': f"/student/projects/{project.id}/",
                'uid': f"project-{project.id}-end",
            })

    milestones = ProjectMilestone.objects.filter(
        project__in=projects, completed=False
    ).select_related('project')
    for milestone in milestones:
        events.append({
            'date': milestone.due_date,
            'time': None,
            'type': 'milestone',
            'title': f"Jalon: {milestone.title}",
            'subtitle': milestone.project.title,
            'url': f"/student/projects/{milestone.project_id}/",
            'uid': f"milestone-{milestone.id}",
        })

    events.sort(key=lambda e: e['date'])
    return events


@login_required
def calendar_view(request):
    """Month-grid calendar of the student's deadlines, milestones and dates."""
    student = get_object_or_404(StudentProfile, user=request.user)

    today = timezone.localtime(timezone.now()).date()
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
        date(year, month, 1)  # validate
    except (TypeError, ValueError):
        year, month = today.year, today.month

    events = collect_student_events(student)
    events_by_date = {}
    for event in events:
        events_by_date.setdefault(event['date'], []).append(event)

    # Build the month grid (weeks starting Monday)
    cal = pycalendar.Calendar(firstweekday=0)
    weeks = []
    for week in cal.monthdatescalendar(year, month):
        week_days = []
        for day in week:
            week_days.append({
                'date': day,
                'in_month': day.month == month,
                'is_today': day == today,
                'events': events_by_date.get(day, []),
            })
        weeks.append(week_days)

    # Previous / next month navigation
    first_of_month = date(year, month, 1)
    prev_month = first_of_month - timedelta(days=1)
    next_month = (first_of_month + timedelta(days=31)).replace(day=1)

    # Upcoming list (next 30 days) shown next to the grid
    upcoming = [e for e in events if today <= e['date'] <= today + timedelta(days=30)]

    month_names = [
        '', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
        'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
    ]

    context = {
        'student': student,
        'weeks': weeks,
        'year': year,
        'month': month,
        'month_name': month_names[month],
        'prev_year': prev_month.year,
        'prev_month': prev_month.month,
        'next_year': next_month.year,
        'next_month': next_month.month,
        'upcoming': upcoming,
        'today': today,
    }
    return render(request, 'student/calendar.html', context)


def _ics_escape(text):
    return (
        str(text)
        .replace('\\', '\\\\')
        .replace(';', '\\;')
        .replace(',', '\\,')
        .replace('\n', '\\n')
    )


@login_required
def calendar_ics(request):
    """iCalendar (.ics) feed of the student's events."""
    student = get_object_or_404(StudentProfile, user=request.user)
    events = collect_student_events(student)

    now_stamp = timezone.now().strftime('%Y%m%dT%H%M%SZ')
    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//ENSA Project Manager//Calendrier étudiant//FR',
        'CALSCALE:GREGORIAN',
        'X-WR-CALNAME:ENSA Project Manager',
    ]

    for event in events:
        lines.append('BEGIN:VEVENT')
        lines.append(f"UID:{event['uid']}@ensa-project-manager")
        lines.append(f"DTSTAMP:{now_stamp}")
        if event['time']:
            # Timed event (assignment deadline)
            dt_utc = event['time'].astimezone(dt_timezone.utc)
            lines.append(f"DTSTART:{dt_utc.strftime('%Y%m%dT%H%M%SZ')}")
        else:
            # All-day event (milestone / project end)
            lines.append(f"DTSTART;VALUE=DATE:{event['date'].strftime('%Y%m%d')}")
        summary = _ics_escape(event['title'])
        if event['subtitle']:
            summary += f" ({_ics_escape(event['subtitle'])})"
        lines.append(f"SUMMARY:{summary}")
        lines.append('END:VEVENT')

    lines.append('END:VCALENDAR')

    response = HttpResponse('\r\n'.join(lines), content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="ensa_calendrier.ics"'
    return response
