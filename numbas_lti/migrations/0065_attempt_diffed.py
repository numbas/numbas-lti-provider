# Generated by Django 2.2.13 on 2021-04-07 08:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('numbas_lti', '0064_auto_20210303_1050'),
    ]

    operations = [
        migrations.AddField(
            model_name='attempt',
            name='diffed',
            field=models.BooleanField(default=False),
        ),
    ]
