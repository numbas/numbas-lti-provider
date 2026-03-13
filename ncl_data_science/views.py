from django.http import Http404
from django.shortcuts import render
from django.views import generic

from .structure import structure

from numbas_lti.models import Resource, Attempt
from numbas_lti.views.lti_13 import resource_launch_handlers
from numbas_lti.views.mixins import reverse_with_lti

class IndexView(generic.TemplateView):
    template_name = 'ncl_data_science/index.html'

def progress_for_resource(resource, user):
    grade = resource.grade_user(user)
    if grade is None:
        return {
            'completion_status': 'not attempted',
            'submitted_at': None,
        }
    else:
        attempt, completion_status, submitted_at = grade
        return {
            'completion_status': completion_status,
            'submitted_at': submitted_at,
        }

class CaseStudiesView(generic.TemplateView):
    template_name = 'ncl_data_science/case_studies.html'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        case_studies = [c.copy() for c in structure['case_studies']]

        for case_study in case_studies:
            resource = Resource.objects.get(pk=case_study['resource_pk'])
            case_study['resource'] = resource
            case_study.update(progress_for_resource(resource, self.request.user))

        context['case_studies'] = case_studies

        return context

status_values = ['not attempted', 'incomplete', 'completed']

def max_completion_status(statuses):
    print('statuses', statuses)
    try:
        return status_values[max(status_values.index(status) for status in statuses)]
    except ValueError:
        return status_values[0]

class TopicsView(generic.TemplateView):
    template_name = 'ncl_data_science/topics.html'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        topics = [t.copy() for t in structure['topics']]

        for topic in topics:
            resources = Resource.objects.filter(pk__in=[s['resource_pk'] for s in topic['subtopics']])
            attempts = Attempt.objects.filter(resource__in=resources)
            completions = []
            for r in resources:
                print(r)
                r_completion = max_completion_status(a.completion_status for a in attempts if a.resource==r)
                completions.append(r_completion)

            topic['completions'] = completions
            if set(completions) == {'completed'}:
                completion_status = 'completed'
            elif 'incomplete' in completions:
                completion_status = 'incomplete'
            else:
                completion_status = 'not attempted'

            topic['completion_status'] = completion_status

        context['topics'] = topics

        return context

class TopicView(generic.TemplateView):
    template_name = 'ncl_data_science/topic.html'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        topic_id = kwargs['topic']
        print(kwargs)
        try:
            topic = next(t for t in structure['topics'] if t['id']==topic_id)
        except StopIteration:
            raise Http404(f"The topic {topic_id} does not exist.")

        for subtopic in topic['subtopics']:
            resource = Resource.objects.get(pk=subtopic['resource_pk'])
            subtopic['resource'] = resource
            subtopic.update(progress_for_resource(resource, self.request.user))

        topic['completion_status'] = 'incomplete'

        context['topic'] = topic

        return context

def handle_data_science_launch(view, *args, **kwargs):
    return redirect(reverse_with_lti('ncl_data_science:case_studies'))

resource_launch_handlers['ncl_data_science'] = handle_data_science_launch
