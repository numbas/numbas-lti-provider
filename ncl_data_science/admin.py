from django.contrib import admin

from .models import Subtopic, Topic, CaseStudy, CaseStudyTopic

class CaseStudyTopicInline(admin.TabularInline):
    model = CaseStudyTopic

@admin.register(CaseStudy)
class CaseStudyAdmin(admin.ModelAdmin):
    inlines = [ CaseStudyTopicInline ]

admin.site.register(Topic)
admin.site.register(Subtopic)
