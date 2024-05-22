from django.contrib import admin

from .models import Resource, Exam, LTIConsumer, LTIConsumerRegistrationToken, SebSettings
# Register your models here.

admin.site.register(Resource)
admin.site.register(Exam)
admin.site.register(LTIConsumer)
admin.site.register(LTIConsumerRegistrationToken)
admin.site.register(SebSettings)
