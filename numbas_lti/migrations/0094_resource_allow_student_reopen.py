# Generated by Django 5.0.6 on 2024-05-30 14:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('numbas_lti', '0093_accesschange_due_date_resource_due_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='resource',
            name='allow_student_reopen',
            field=models.BooleanField(default=True, verbose_name='Allow students to re-open attempts while the resource is available?'),
        ),
    ]
