# Generated by Django 3.2.16 on 2023-10-26 10:18

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

def make_lti_11_user_aliases(apps, schema_editor):
    LTIUserData = apps.get_model('numbas_lti', 'LTIUserData')
    LTI_11_UserAlias = apps.get_model('numbas_lti', 'LTI_11_UserAlias')
    User = apps.get_model('auth', 'User')
    LTIConsumer = apps.get_model('numbas_lti', 'LTIConsumer')

    for consumer_pk, user_pk, consumer_user_id in LTIUserData.objects.all().values_list('consumer', 'user', 'consumer_user_id').distinct():
        consumer = LTIConsumer.objects.get(pk=consumer_pk)
        user = User.objects.get(pk=user_pk)

        LTI_11_UserAlias.objects.create(
            consumer=consumer,
            user=user,
            consumer_user_id=consumer_user_id
        )


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('numbas_lti', '0077_auto_20231026_0914'),
    ]

    operations = [
        migrations.CreateModel(
            name='LTI_11_UserAlias',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('consumer_user_id', models.TextField()),
                ('consumer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_aliases', to='numbas_lti.lticonsumer')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lti_11_aliases', to=settings.AUTH_USER_MODEL)),
            ],
        ),

        migrations.RunPython(make_lti_11_user_aliases, migrations.RunPython.noop),
    ]