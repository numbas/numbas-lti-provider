# Generated by Django 5.0.7 on 2024-10-23 06:28

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('numbas_lti', '0096_accesschange_due_date_resource_allow_student_reopen_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UserScoreReported',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('time', models.DateTimeField(auto_now_add=True, help_text='The time that the score was reported.')),
                ('error', models.TextField(blank=True, help_text='The text of any error message returned by the consumer.', null=True, verbose_name='Error message')),
                ('raw_score', models.FloatField()),
                ('max_score', models.FloatField()),
                ('completion_status', models.CharField(choices=[('not attempted', 'Not started'), ('incomplete', 'In progress'), ('completed', 'Complete')], max_length=20)),
                ('start_time', models.DateTimeField()),
                ('submitted_time', models.DateTimeField(blank=True, null=True)),
                ('attempt', models.ForeignKey(help_text='Attempt whose score was used for this report.', null=True, on_delete=django.db.models.deletion.SET_NULL, to='numbas_lti.attempt')),
                ('report_process', models.ForeignKey(help_text='Resource score reporting process that this was a part of.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='user_score_reports', to='numbas_lti.reportprocess')),
                ('resource', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_scores_reported', to='numbas_lti.resource')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reported_scores', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('time',),
            },
        ),
    ]
