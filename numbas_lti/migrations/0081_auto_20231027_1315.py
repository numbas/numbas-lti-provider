# Generated by Django 3.2.16 on 2023-10-27 13:15

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('numbas_lti', '0080_auto_20231027_1301'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lti_11_resourcelink',
            name='context',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='lti_11_resource_links', to='numbas_lti.lticontext'),
        ),
        migrations.CreateModel(
            name='LTI_13_ResourceLink',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('resource_link_id', models.CharField(max_length=300)),
                ('title', models.CharField(default='', max_length=300)),
                ('description', models.TextField(default='')),
                ('context', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='lti_13_resource_links', to='numbas_lti.lticontext')),
                ('resource', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lti_13_links', to='numbas_lti.resource')),
            ],
        ),
    ]