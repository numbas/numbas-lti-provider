# Generated by Django 5.1.4 on 2025-02-13 15:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('numbas_lti', '0100_contextsummary_contextsummaryresource_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='contextsummary',
            name='layout',
            field=models.CharField(choices=[('compact', 'Compact'), ('table', 'Table')], default='compact', max_length=10, verbose_name='Layout'),
        ),
    ]
