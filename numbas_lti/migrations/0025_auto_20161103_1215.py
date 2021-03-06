# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2016-11-03 12:15
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('numbas_lti', '0024_auto_20161103_1124'),
    ]

    operations = [
        migrations.AddField(
            model_name='lticonsumer',
            name='deleted',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='lticonsumer',
            name='key',
            field=models.CharField(help_text='The key should be human-readable, and uniquely identify this consumer.', max_length=100, unique=True, verbose_name='Consumer key'),
        ),
        migrations.AlterField(
            model_name='lticonsumer',
            name='secret',
            field=models.CharField(max_length=100, verbose_name='Consumer secret'),
        ),
    ]
