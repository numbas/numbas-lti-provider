# Generated by Django 5.0.7 on 2024-12-19 09:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('numbas_lti', '0097_userscorereported'),
    ]

    operations = [
        migrations.AddField(
            model_name='accesschange',
            name='initial_seed',
            field=models.CharField(blank=True, default='', max_length=20, verbose_name='Initial seed for the random number generator'),
        ),
    ]
