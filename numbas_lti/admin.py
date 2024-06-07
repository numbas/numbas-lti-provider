from django.contrib import admin

from .models import Resource, Exam, LTIConsumer, LTI_11_Consumer, LTI_13_Consumer, LTIConsumerRegistrationToken, SebSettings
# Register your models here.

class LTI_11_ConsumerInline(admin.TabularInline):
    model = LTI_11_Consumer

class LTI_13_ConsumerInline(admin.TabularInline):
    model = LTI_13_Consumer

@admin.register(LTIConsumer)
class LTIConsumerAdmin(admin.ModelAdmin):
    inlines = [ LTI_11_ConsumerInline, LTI_13_ConsumerInline ]

admin.site.register(Resource)
admin.site.register(Exam)
admin.site.register(LTIConsumerRegistrationToken)
admin.site.register(SebSettings)
