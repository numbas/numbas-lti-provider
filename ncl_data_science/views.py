from django.http import Http404
from django.shortcuts import render
from django.views import generic

from .models import CaseStudy, Topic

from numbas_lti.models import Resource, Attempt
from numbas_lti.views.lti_13 import resource_launch_handlers
from numbas_lti.views.mixins import reverse_with_lti

class IndexView(generic.TemplateView):
    template_name = 'ncl_data_science/index.html'

class CaseStudiesView(generic.ListView):
    model = CaseStudy
    template_name = 'ncl_data_science/case_studies.html'
    context_object_name = 'case_studies'

    def get_queryset(self):
        objects = super().get_queryset()
        return [(case_study, case_study.progress_for_user(self.request.user)) for case_study in objects]


class TopicsView(generic.ListView):
    model =  Topic
    template_name = 'ncl_data_science/topics.html'
    context_object_name = 'topics'

    def get_queryset(self):
        objects = super().get_queryset()
        return [(topic, topic.progress_for_user(self.request.user)) for topic in objects]


class TopicView(generic.DetailView):
    model = Topic
    template_name = 'ncl_data_science/topic.html'
    context_object_name = 'topic'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)

        topic = self.object

        context['topic_progress'] = topic.progress_for_user(self.request.user)

        context['completion_status'] = topic.progress_for_user(self.request.user)

        context['subtopics'] = [(subtopic, subtopic.progress_for_user(self.request.user)) for subtopic in topic.subtopics.all()]

        case_studies = topic.case_studies.all()
        context['case_studies'] = [(case_study, case_study.progress_for_user(self.request.user)) for case_study in case_studies]

        return context

def handle_data_science_launch(view, *args, **kwargs):
    return redirect(reverse_with_lti('ncl_data_science:case_studies'))

resource_launch_handlers['ncl_data_science'] = handle_data_science_launch
