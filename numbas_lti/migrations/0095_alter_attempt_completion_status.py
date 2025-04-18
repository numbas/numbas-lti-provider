# Generated by Django 5.0.7 on 2024-10-11 13:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('numbas_lti', '0094_lti_13_context_cached_lineitems_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='attempt',
            name='completion_status',
            field=models.CharField(choices=[('not attempted', 'Not started'), ('incomplete', 'In progress'), ('completed', 'Complete')], default='not attempted', max_length=20),
        ),
    ]
