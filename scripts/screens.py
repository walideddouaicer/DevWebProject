"""Screenshot + accessibility harness (PLAN P5.2).

    .venv/bin/python scripts/screens.py                 # everything -> screens/current/
    .venv/bin/python scripts/screens.py --set before    # -> screens/before/
    .venv/bin/python scripts/screens.py --only project_detail --role student
    .venv/bin/python scripts/screens.py --widths 1440 --themes light

It seeds a throwaway SQLite DB (never the dev DB), starts its own runserver, logs in as
each role through the real login form, and for every GET page captures full-page PNGs at
each width x theme. It also runs axe-core on each page (desktop, light) and records console
errors and CSP violations. Results: screens/<set>/<role>/<url-name>__<width>__<theme>.png,
screens/<set>/a11y.json and screens/<set>/report.md.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
PY = str(ROOT / ".venv" / "bin" / "python")
PORT = 8765
BASE = f"http://127.0.0.1:{PORT}"
PASSWORD = "demo12345!"

ROLES = {
    "anon": None,
    "student": "etu.youssef",  # owns a 3-person team project, has invitations/notifications
    "teacher": "prof.alami",
    "admin": "admin",
}
SAMPLE_QUERY = {"search:search": "?q=web", "search:search_projects": "?q=web"}
NAMESPACE_ROLE = {"student": "student", "teacher": "teacher", "administrator": "admin"}


def django_env(workdir):
    env = dict(os.environ)
    env.update(
        ENVIRONMENT="dev",
        DJANGO_DEBUG="True",
        DATABASE_URL=f"sqlite:///{workdir}/screens.sqlite3",
        MEDIA_ROOT=f"{workdir}/media",
        PRIVATE_MEDIA_ROOT=f"{workdir}/private",
        DJANGO_ALLOWED_HOSTS="127.0.0.1,localhost",
        DJANGO_SETTINGS_MODULE="ensa_project_manager.settings",
    )
    return env


def discover_pages(env):
    """(role, url_name, path) for every GET route, with sample ids from the seeded DB."""
    code = r"""
import json, django
django.setup()
from django.urls import URLPattern, URLResolver, get_resolver, reverse
from student.models import Project, Notification, CollaborationInvitation, StudentProfile
from teacher.models import Module, ModuleAssignment, ProjectOption, ProjectAssignment
from accounts.models import PendingRegistration
from django.contrib.auth.models import User
youssef = StudentProfile.objects.get(user__username="etu.youssef")
project = Project.objects.get(student=youssef, project_assignment__module__code="WEB401")
web = Module.objects.get(code="WEB401")
direct = ProjectAssignment.objects.filter(module=web, assignment_type="direct").first()
public = Project.objects.filter(is_public=True).first()
ids = {
    "project_id": project.id, "module_id": web.id, "assignment_id": project.project_assignment_id,
    "milestone_id": project.milestones.first().id, "deliverable_id": project.deliverables.first().id,
    "invitation_id": CollaborationInvitation.objects.first().id,
    "collaborator_id": project.collaborators.first().id,
    "option_id": ProjectOption.objects.filter(assignment=project.project_assignment).last().id,
    "notification_id": Notification.objects.first().id,
    "registration_id": PendingRegistration.objects.first().id,
    "student_id": youssef.id, "user_id": youssef.user_id, "uidb64": "MQ", "token": "x",
    "new_status": "submitted", "response": "accept",
}
overrides = {
    "public:project_detail": {"project_id": public.id},
    "public:report_project": {"project_id": public.id},
    "teacher:assignment_students": {"assignment_id": direct.id},
    "administrator:remove_assignment": {"assignment_id": ModuleAssignment.objects.first().id},
}
out = []
def walk(patterns, ns=""):
    for p in patterns:
        if isinstance(p, URLResolver):
            if p.app_name != "admin":
                walk(p.url_patterns, f"{ns}{p.namespace}:" if p.namespace else ns)
        elif isinstance(p, URLPattern) and p.name:
            name = f"{ns}{p.name}"
            kwargs = {**ids, **overrides.get(name, {})}
            try:
                out.append([name, reverse(name, kwargs={k: kwargs[k] for k in p.pattern.converters})])
            except Exception:
                pass
walk(get_resolver().url_patterns)
print(json.dumps(out))
"""
    result = subprocess.run([PY, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True)
    if result.returncode:
        sys.exit(result.stderr)
    pages = []
    for name, path in json.loads(result.stdout.strip().splitlines()[-1]):
        role = NAMESPACE_ROLE.get(name.split(":")[0]) if ":" in name else None
        if role:
            roles = [role]
        elif name.startswith("search:"):
            roles, path = list(ROLES), path + SAMPLE_QUERY.get(name, "")
        else:
            roles = ["anon", "student"] if name.startswith("public:") else ["anon"]
        for r in roles:
            pages.append((r, name, path))
    return pages


def start_server(env):
    server = subprocess.Popen(
        [PY, "manage.py", "runserver", f"127.0.0.1:{PORT}", "--noreload", "--nothreading"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(60):
        try:
            urllib.request.urlopen(f"{BASE}/healthz", timeout=1)
            return server
        except Exception:
            time.sleep(0.5)
    server.kill()
    sys.exit("server did not start")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", default="current")
    parser.add_argument("--only", help="substring of the URL name")
    parser.add_argument("--role", choices=list(ROLES))
    parser.add_argument("--widths", default="1440,390")
    parser.add_argument("--themes", default="light,dark")
    parser.add_argument("--no-a11y", action="store_true")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 on any console error, CSP violation or serious/critical a11y issue",
    )
    args = parser.parse_args()

    from playwright.sync_api import sync_playwright

    workdir = tempfile.mkdtemp(prefix="screens-")
    env = django_env(workdir)
    subprocess.run([PY, "manage.py", "migrate", "-v0"], cwd=ROOT, env=env, check=True)
    subprocess.run(
        [PY, "manage.py", "seed_demo"], cwd=ROOT, env=env, check=True, capture_output=True
    )
    pages = [
        p
        for p in discover_pages(env)
        if (not args.only or args.only in p[1]) and (not args.role or p[0] == args.role)
    ]
    out_dir = ROOT / "screens" / args.set
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True)
    axe = (ROOT / "scripts" / "vendor" / "axe.min.js").read_text()
    widths = [int(w) for w in args.widths.split(",")]
    themes = args.themes.split(",")

    server = start_server(env)
    a11y, problems, shots = {}, [], 0
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            for role, username in ROLES.items():
                role_pages = [p for p in pages if p[0] == role]
                if not role_pages:
                    continue
                storage = None
                if username:
                    context = browser.new_context()
                    page = context.new_page()
                    page.goto(f"{BASE}/login/")
                    page.fill("input[name=username]", username)
                    page.fill("input[name=password]", PASSWORD)
                    page.click("form [type=submit]")
                    page.wait_for_load_state("networkidle")
                    storage = context.storage_state()
                    context.close()
                for theme in themes:
                    for width in widths:
                        context = browser.new_context(
                            storage_state=storage,
                            viewport={"width": width, "height": 900 if width > 600 else 844},
                            color_scheme=theme,
                            device_scale_factor=1,
                        )
                        page = context.new_page()
                        messages = []
                        page.on(
                            "console",
                            lambda m, messages=messages: (
                                messages.append(m.text) if m.type == "error" else None
                            ),
                        )
                        for _, name, path in role_pages:
                            messages.clear()
                            try:
                                response = page.goto(
                                    BASE + path, wait_until="networkidle", timeout=30000
                                )
                            except Exception as error:
                                if "Download is starting" in str(error):
                                    continue  # file export, not a page
                                problems.append(
                                    {
                                        "role": role,
                                        "page": name,
                                        "errors": [str(error)[:200]],
                                        "csp": 0,
                                    }
                                )
                                continue
                            status = response.status if response else 0
                            content_type = (
                                response.headers.get("content-type", "") if response else ""
                            )
                            if (
                                status != 200
                                or "text/html" not in content_type
                                or urlparse(page.url).path != urlparse(BASE + path).path
                            ):
                                continue  # POST-only, redirect, file download or permission page
                            if not page.evaluate("!!document.querySelector('main')"):
                                continue  # HTMX fragment, not a page
                            slug = name.replace(":", "_")
                            target = out_dir / role / f"{slug}__{width}__{theme}.png"
                            target.parent.mkdir(parents=True, exist_ok=True)
                            try:
                                page.screenshot(
                                    path=str(target),
                                    full_page=True,
                                    animations="disabled",
                                    timeout=60000,
                                )
                                shots += 1
                            except Exception as error:  # keep going; report it
                                problems.append(
                                    {
                                        "role": role,
                                        "page": name,
                                        "errors": [f"screenshot: {error}"[:200]],
                                        "csp": 0,
                                    }
                                )
                            csp = [m for m in messages if "Content Security Policy" in m]
                            errors = [m for m in messages if m not in csp]
                            if errors or (csp and theme == themes[0] and width == widths[0]):
                                problems.append(
                                    {
                                        "role": role,
                                        "page": name,
                                        "errors": errors[:5],
                                        "csp": len(csp),
                                    }
                                )
                            if not args.no_a11y and theme == themes[0] and width == widths[0]:
                                # Evaluated through the DevTools protocol: an injected
                                # <script> tag would be blocked by the enforced CSP.
                                page.evaluate(f"() => {{ {axe}\n }}")
                                result = page.evaluate(
                                    "async () => (await axe.run(document, {resultTypes: ['violations']})).violations"
                                    ".map(v => ({id: v.id, impact: v.impact, nodes: v.nodes.length, help: v.help}))"
                                )
                                a11y[f"{role}:{name}"] = result
                        context.close()
            browser.close()
    finally:
        server.terminate()
        shutil.rmtree(workdir, ignore_errors=True)

    (out_dir / "a11y.json").write_text(json.dumps(a11y, indent=2, ensure_ascii=False))
    serious = {
        k: [v for v in vs if v["impact"] in ("serious", "critical")] for k, vs in a11y.items()
    }
    serious = {k: v for k, v in serious.items() if v}
    lines = [
        f"# Screens report ({args.set})",
        "",
        f"{shots} screenshots, {len(a11y)} pages audited, {len(serious)} with serious/critical a11y issues.",
        "",
        "## Serious/critical accessibility issues",
    ]
    for key, violations in sorted(serious.items()):
        lines.append(f"- **{key}**: " + ", ".join(f"{v['id']} ({v['nodes']})" for v in violations))
    lines += ["", "## Console errors / CSP violations"]
    for p in problems:
        lines.append(f"- **{p['role']}:{p['page']}** CSP={p['csp']} errors={p['errors']}")
    (out_dir / "report.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:4]))
    print(f"{len(problems)} page(s) with console errors / CSP violations.")
    if args.strict and (problems or serious):
        for p in problems:
            print(f"  {p['role']}:{p['page']} CSP={p['csp']} errors={p['errors']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
