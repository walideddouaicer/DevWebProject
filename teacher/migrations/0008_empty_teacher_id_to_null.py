from django.db import migrations


def forwards(apps, schema_editor):
    # '' collides with the unique constraint; "no ID" must be NULL (PLAN B9).
    apps.get_model("teacher", "TeacherProfile").objects.filter(teacher_id="").update(teacher_id=None)


class Migration(migrations.Migration):
    dependencies = [("teacher", "0007_moduleannouncement")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
