# Generated by Django 3.2.8 on 2022-04-05 08:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('numbas_lti', '0071_nullable_last_cache_update'),
    ]

    operations = [
        migrations.AlterField(
            model_name='editorlink',
            name='last_cache_update',
            field=models.DateTimeField(blank=True, editable=False, null=True, verbose_name='Time of last cache update'),
        ),
    ]
