from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('numbas_lti', '0070_auto_20211020_1236'),
    ]

    operations = [
        migrations.AlterField(
            model_name="editorlink",
            name="last_cache_update",
            field=models.DateTimeField(null=True)
        ),
    ]
