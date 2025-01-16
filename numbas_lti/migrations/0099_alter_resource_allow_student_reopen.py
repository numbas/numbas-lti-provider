# Generated by Django 5.1.4 on 2025-01-16 08:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('numbas_lti', '0098_accesschange_initial_seed'),
    ]

    operations = [
        migrations.AlterField(
            model_name='resource',
            name='allow_student_reopen',
            field=models.BooleanField(default=False, verbose_name='Allow students to re-open attempts while the resource is available?'),
        ),
    ]
