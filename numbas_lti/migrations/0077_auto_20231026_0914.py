# Generated by Django 3.2.16 on 2023-10-26 09:14

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('numbas_lti', '0076_lti_11_consumer'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='lticonsumer',
            name='key',
        ),
        migrations.RemoveField(
            model_name='lticonsumer',
            name='secret',
        ),
    ]
