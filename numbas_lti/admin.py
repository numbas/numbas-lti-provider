from django.contrib import admin

from .models import Resource, Exam, LTIConsumer
# Register your models here.

admin.site.register(Resource)
admin.site.register(Exam)
admin.site.register(LTIConsumer)
