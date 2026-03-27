from django.contrib import admin

from .models import Subtopic, Topic, CaseStudy, CaseStudyTopic

class CaseStudyTopicInline(admin.TabularInline):
    model = CaseStudyTopic

@admin.register(CaseStudy)
class CaseStudyAdmin(admin.ModelAdmin):
    inlines = [ CaseStudyTopicInline ]

class SubtopicInline(admin.TabularInline):
    model = Subtopic

@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    inlines = [ SubtopicInline ]

admin.site.register(Subtopic)
