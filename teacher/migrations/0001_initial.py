# Generated by Django 5.2.1 on 2025-05-07 20:50

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="TeacherProfile",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "teacher",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="accounts.teacher",
                    ),
                ),
            ],
        ),
    ]
