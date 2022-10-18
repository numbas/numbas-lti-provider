from django.contrib import admin

from .models import Resource, Exam, LTIConsumer, SebSettings
# Register your models here.

admin.site.register(Resource)
admin.site.register(Exam)
admin.site.register(LTIConsumer)
admin.site.register(SebSettings)
