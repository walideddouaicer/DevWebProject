from django.db import migrations


def forwards(apps, schema_editor):
    apps.get_model("administrator", "AdminProfile").objects.filter(admin_id="").update(admin_id=None)


class Migration(migrations.Migration):
    dependencies = [("administrator", "0001_initial")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
