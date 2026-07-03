# Backfill deliverable versions: existing same-name uploads on a project
# are numbered v1, v2, ... in upload order (ROADMAP #11).
from django.db import migrations


def backfill_versions(apps, schema_editor):
    ProjectDeliverable = apps.get_model('student', 'ProjectDeliverable')

    seen = {}
    for deliverable in ProjectDeliverable.objects.order_by('project_id', 'name', 'upload_date', 'id'):
        key = (deliverable.project_id, deliverable.name)
        seen[key] = seen.get(key, 0) + 1
        if deliverable.version != seen[key]:
            deliverable.version = seen[key]
            deliverable.save(update_fields=['version'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('student', '0018_projectdeliverable_version'),
    ]

    operations = [
        migrations.RunPython(backfill_versions, noop),
    ]
