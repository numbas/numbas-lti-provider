# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('numbas_lti', '0018_lti_consumer'),
    ]

    operations = [
        migrations.AddField(
            model_name='ltiuserdata',
            name='consumer_user_id',
            field=models.TextField(blank=True, default='', null=True),
        ),
    ]

