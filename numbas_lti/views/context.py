from django.views import generic
from django.shortcuts import render, redirect
from numbas_lti.models import LTIContext, ContextSummary, COMPLETION_STATUSES
from .consumer import ConsumerManagementMixin
from .mixins import MustBeInstructorMixin, request_is_instructor
from numbas_lti import forms
from django.urls import reverse

class ManageContextView(ConsumerManagementMixin, generic.detail.DetailView):
    model = LTIContext
    context_object_name = 'context'
    template_name = 'numbas_lti/management/admin/context/view.html'

class DeleteContextView(ConsumerManagementMixin, generic.DeleteView):
    model = LTIContext
    context_object_name = 'context'
    template_name = 'numbas_lti/management/admin/context/confirm_delete.html'

    def get_success_url(self):
        return reverse('view_consumer', args=(self.object.consumer.pk,))

class CreateContextSummaryView(MustBeInstructorMixin, generic.edit.CreateView):
    model = ContextSummary
    template_name = 'numbas_lti/management/context_summary/edit.html'
    form_class = forms.CreateContextSummaryForm

    def get_success_url(self):
        return self.reverse_with_lti('context_summary',args=(self.object.pk,))

class UpdateContextSummaryView(MustBeInstructorMixin, generic.edit.UpdateView):
    model = ContextSummary
    template_name = 'numbas_lti/management/context_summary/edit.html'
    form_class = forms.UpdateContextSummaryForm

    def get_success_url(self):
        return self.reverse_with_lti('context_summary',args=(self.object.pk,))

class ContextSummaryView(generic.detail.DetailView):
    model = ContextSummary
    context_object_name = 'summary'

    def dispatch(self, request, *args, **kwargs):
        self.is_instructor = request_is_instructor(self.request)

        return super().dispatch(request, *args, **kwargs)

    def get_template_names(self):
        if self.is_instructor:
            return ['numbas_lti/management/context_summary/view.html']
        else:
            return ['numbas_lti/context_summary.html']

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)

        cs = self.object

        completion_status_displays = dict(COMPLETION_STATUSES)

        user = self.request.user

        def resource_summary(resource):
            res = resource.grade_user(user)

            r = {
                'resource': resource,
                'attempt': None,
                'scaled_score': 0,
                'completion_status': 'not attempted',
                'raw_score': 0,
                'max_score': resource.estimate_max_score(),
                'is_available': resource.is_available(user)
            }

            if res:
                attempt, completion_status, submitted_at = res

                r.update({
                    'resource': resource,
                    'attempt': attempt,
                    'scaled_score': attempt.scaled_score,
                    'raw_score': attempt.raw_score,
                    'max_score': attempt.max_score,
                    'completion_status': completion_status,
                    'submitted_at': submitted_at,
                })

            r['completed'] = r['scaled_score'] == 1

            if cs.show_total_score == 'completion':
                r['completed'] = r['completed'] or r['completion_status'] == 'completed'

            r['completion_status_display'] = completion_status_displays[r['completion_status'] if not r['completed'] else 'completed']

            return r

        resources = [resource_summary(r) for r in cs.ordered_resources().all()]

        num_completed = len([r for r in resources if r['completed']])

        proportion_completed = num_completed / len(resources)

        if cs.show_total_score == 'scaled':
            context['total_score'] = sum(r['scaled_score'] for r in resources)
            context['max_score'] = len(resources)
        elif cs.show_total_score == 'raw':
            context['total_score'] = sum(r['raw_score'] for r in resources)
            context['max_score'] = sum(r['max_score'] for r in resources)
        elif cs.show_total_score == 'completion':
            context['total_score'] = len([r for r in resources if r['completed']])
            context['max_score'] = len(resources)
        elif cs.show_total_score == 'max_scores':
            context['total_score'] = len([r for r in resources if r['scaled_score'] == 1])
            context['max_score'] = len(resources)
        else:
            context['total_score'] = 0
            context['max_score'] = 1

        context['scaled_score'] = context['total_score'] / context['max_score']

        context.update({
            'resources': resources,
            'num_completed': num_completed,
            'proportion_completed': proportion_completed,
        })

        return context
