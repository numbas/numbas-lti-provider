# Generated by Django 5.0.6 on 2024-07-03 15:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('numbas_lti', '0091_alter_lticonsumerregistrationtoken_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='resource',
            name='lineitem_unwanted',
            field=models.BooleanField(default=False, verbose_name='Grades service line item unwanted?'),
        ),
    ]
