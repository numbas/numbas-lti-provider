# Generated by Django 3.2.15 on 2022-12-01 08:45

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    replaces = [('numbas_lti', '0073_resource_require_lockdown_app'), ('numbas_lti', '0074_alter_lticontext_unique_together'), ('numbas_lti', '0075_auto_20221018_1102')]

    dependencies = [
        ('numbas_lti', '0072_alter_editorlink_last_cache_update'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='lticontext',
            unique_together={('context_id', 'instance_guid')},
        ),
        migrations.CreateModel(
            name='SebSettings',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='A descriptive name for this settings file.', max_length=200, verbose_name='Name')),
                ('settings_file', models.FileField(help_text='Save the settings file and upload it here.', upload_to='seb_settings/', verbose_name='Settings file')),
                ('config_key_hash', models.CharField(help_text='Turn on <strong>Use Browser Exam Key and Configuration Key</strong>, and paste the Configuration Key in the tool here.', max_length=64, verbose_name='Configuration key')),
                ('password', models.CharField(blank=True, help_text='If you set a <strong>Settings password</strong> and would like the Numbas LTI tool to show it to the student, paste it here.', max_length=30, verbose_name='Password')),
            ],
        ),
        migrations.AddField(
            model_name='resource',
            name='lockdown_app_password',
            field=models.CharField(blank=True, max_length=30, verbose_name='Password for the Numbas lockdown app'),
        ),
        migrations.AddField(
            model_name='resource',
            name='show_lockdown_app_password',
            field=models.BooleanField(default=False, verbose_name='Show the password for the lockdown app on the launch page?'),
        ),
        migrations.AddField(
            model_name='resource',
            name='require_lockdown_app',
            field=models.CharField(blank=True, choices=[('', 'No'), ('numbas', 'Numbas lockdown app'), ('seb', 'Safe Exam Browser')], default='', max_length=20, verbose_name='Require a lockdown app?'),
        ),
        migrations.AddField(
            model_name='resource',
            name='seb_settings',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='resources', to='numbas_lti.sebsettings'),
        ),
    ]
