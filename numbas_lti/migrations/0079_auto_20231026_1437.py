# Generated by Django 3.2.16 on 2023-10-26 14:37

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('lti1p3_tool_config', '0002_alter_ltitool_id_alter_ltitoolkey_id'),
        ('numbas_lti', '0078_lti_11_useralias'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lti_11_useralias',
            name='consumer',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lti_11_user_aliases', to='numbas_lti.lticonsumer'),
        ),
        migrations.CreateModel(
            name='LTI_13_UserAlias',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sub', models.CharField(max_length=255)),
                ('full_name', models.CharField(blank=True, default='', max_length=1000)),
                ('given_name', models.CharField(blank=True, default='', max_length=1000)),
                ('family_name', models.CharField(blank=True, default='', max_length=1000)),
                ('email', models.EmailField(blank=True, default='', max_length=254)),
                ('locale', models.CharField(blank=True, default='', max_length=30)),
                ('consumer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lti_13_user_aliases', to='numbas_lti.lticonsumer')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lti_13_aliases', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='LTI_13_Consumer',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('consumer', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='lti_13', to='numbas_lti.lticonsumer')),
                ('tool', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='numbas', to='lti1p3_tool_config.ltitool')),
            ],
        ),
    ]