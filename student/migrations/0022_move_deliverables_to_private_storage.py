"""Move already-uploaded deliverables from public MEDIA_ROOT to PRIVATE_MEDIA_ROOT.

File names in the database stay the same (e.g. "deliverables/report.pdf"); only the
root directory changes. Missing files are skipped (they were already broken).
"""

import os
import shutil

from django.conf import settings
from django.db import migrations


def move_files(apps, schema_editor, source_root, target_root):
    ProjectDeliverable = apps.get_model("student", "ProjectDeliverable")
    for name in ProjectDeliverable.objects.exclude(file="").values_list("file", flat=True):
        source = os.path.join(source_root, name)
        target = os.path.join(target_root, name)
        if os.path.exists(source) and not os.path.exists(target):
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.move(source, target)


def forwards(apps, schema_editor):
    move_files(apps, schema_editor, settings.MEDIA_ROOT, settings.PRIVATE_MEDIA_ROOT)


def backwards(apps, schema_editor):
    move_files(apps, schema_editor, settings.PRIVATE_MEDIA_ROOT, settings.MEDIA_ROOT)


class Migration(migrations.Migration):
    dependencies = [("student", "0021_private_deliverables")]

    operations = [migrations.RunPython(forwards, backwards)]
