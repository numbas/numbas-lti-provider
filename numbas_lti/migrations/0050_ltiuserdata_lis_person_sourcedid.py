# Generated by Django 2.2.4 on 2019-11-07 11:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('numbas_lti', '0049_lticonsumer_identifier_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='ltiuserdata',
            name='lis_person_sourcedid',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
    ]
