from django.contrib.auth.models import User
from django.shortcuts import render,redirect
from django.utils.decorators import available_attrs
from django.views.decorators.csrf import csrf_exempt
from django_auth_lti.decorators import lti_role_required
from django_auth_lti.const import LEARNER, INSTRUCTOR
from django_auth_lti.patch_reverse import patch_reverse
from django_auth_lti.mixins import LTIRoleRestrictionMixin
from django.views import generic
from django.core.urlresolvers import reverse
from django.core.exceptions import PermissionDenied
from django import http
import json

patch_reverse()

from functools import wraps

from .models import LTIUserData, Resource, AccessToken, Exam, Attempt, ScormElement
from .forms import ResourceSettingsForm

# Create your views here.
@csrf_exempt
def index(request):
    context = {
        'entry_url': request.build_absolute_uri(reverse('lti_entry')),
    }
    return render(request,'numbas_lti/index.html',context)

def request_is_instructor(request):
    return 'Instructor' in request.LTI.get('roles')

@csrf_exempt
def lti_entry(request):
    user_data,_ = LTIUserData.objects.get_or_create(
        user=request.user,
        resource=request.resource
    )
    user_data.lis_result_sourcedid = request.POST.get('lis_result_sourcedid')
    user_data.lis_outcome_service_url = request.POST.get('lis_outcome_service_url')
    user_data.save()

    if request_is_instructor(request):
        if not request.resource.exam:
            return redirect(reverse('create_exam'))
        else:
            return redirect(reverse('manage_resource',args=(request.resource.pk,)))
    else:
        if not request.resource.exam:
            return render(request,'numbas_lti/exam_not_set_up.html',{})
        else:
            return redirect(reverse('show_attempts'))

class MustBeInstructorMixin(LTIRoleRestrictionMixin):
    allowed_roles = ['Instructor']

class CreateExamView(MustBeInstructorMixin,generic.edit.CreateView):
    model = Exam
    fields = ['package']
    template_name = 'numbas_lti/create_exam.html'

    def form_valid(self,form):
        self.object = form.save()
        self.request.resource.exam = self.object
        self.request.resource.save()
        return http.HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse('manage_resource',args=(self.request.resource.pk,))

class ManageResourceView(MustBeInstructorMixin,generic.detail.DetailView):
    model = Resource
    template_name = 'numbas_lti/manage_resource.html'
    context_object_name = 'resource'

    def get_context_data(self,*args,**kwargs):
        context = super(ManageResourceView,self).get_context_data(*args,**kwargs)

        resource = self.get_object()
        context['student_summary'] = [
            (
                student,
                resource.grade_user(student),
                Attempt.objects.filter(user=student,resource=resource).count(),
                AccessToken.objects.filter(user=student,resource=resource).count(),
            ) 
            for student in resource.students().all()
        ]

        return context

class ResourceSettingsView(MustBeInstructorMixin,generic.edit.UpdateView):
    model = Resource
    form_class = ResourceSettingsForm
    template_name = 'numbas_lti/resource_settings.html'
    context_object_name = 'resource'

    def get_success_url(self):
        return reverse('manage_resource',args=(self.get_object().pk,))


@lti_role_required(['Instructor'])
def grant_access_token(request,user_id):
    user = User.objects.get(id=user_id)
    AccessToken.objects.create(user=user,resource=request.resource)

    return redirect(reverse('manage_resource',args=(request.resource.pk,)))

class RunExamView(generic.detail.DetailView):
    """
        Run an exam without saving any attempt data
    """
    model = Exam
    template_name = 'numbas_lti/run_exam.html'

    def get_context_data(self,*args,**kwargs):
        context = super(RunExamView,self).get_context_data(*args,**kwargs)

        context['scorm_cmi'] = json.dumps({
            'cmi.mode': 'normal',
            'cmi.entry': 'ab-initio',
            'cmi.suspend_data': '',
            'cmi.objectives._count': 0,
            'cmi.interactions._count': 0,
            'cmi.learner_name': self.request.user.get_full_name(),
            'cmi.learner_id': self.request.user.username,
            'cmi.location': '',
            'cmi.score.raw': 0,
            'cmi.score.scaled': 0,
            'cmi.score.min': 0,
            'cmi.score.max': 0,
            'cmi.total_time': 0,
            'cmi.completion_status': '',
            'cmi.success_status': ''
        })
        
        return context

class ShowAttemptsView(generic.list.ListView):
    model = Attempt
    template_name = 'numbas_lti/show_attempts.html'

    ordering = ['start_time']

    def get_queryset(self):
        return Attempt.objects.filter(resource=self.request.resource,user=self.request.user)

    def dispatch(self,request,*args,**kwargs):
        if not self.get_queryset().exists():
            return new_attempt(request)
        else:
            return super(ShowAttemptsView,self).dispatch(request,*args,**kwargs)

    def get_context_data(self,*args,**kwargs):
        context = super(ShowAttemptsView,self).get_context_data(*args,**kwargs)

        context['can_start_new_attempt'] = self.request.resource.can_start_new_attempt(self.request.user)
        
        return context

def new_attempt(request):
    if not request.resource.can_start_new_attempt(request.user):
        raise PermissionDenied("You can't start a new attempt at this exam")

    if Attempt.objects.filter(resource=request.resource,user=request.user).count()==request.resource.max_attempts:
        AccessToken.objects.filter(resource=request.resource,user=request.user).first().delete()

    attempt = Attempt.objects.create(
        resource = request.resource,
        exam = request.resource.exam,
        user = request.user
    )
    return redirect(reverse('run_attempt',args=(attempt.pk,)))

class RunAttemptView(generic.detail.DetailView):
    model = Attempt
    context_object_name = 'attempt'

    template_name = 'numbas_lti/run_attempt.html'

    def get_context_data(self,*args,**kwargs):
        context = super(RunAttemptView,self).get_context_data(*args,**kwargs)

        attempt = self.get_object()

        if attempt.completion_status=='completed':
            mode = 'review'
        else:
            mode = 'normal'

        if attempt.user != self.request.user:
            if request_is_instructor(self.request):
                mode = 'review'
            else:
                raise PermissionDenied("You're not allowed to review this attempt.")

        scorm_cmi = {
            'cmi.mode': mode,
            'cmi.entry': 'ab-initio' if attempt.completion_status=='not attempted' else 'resume',
            'cmi.suspend_data': '',
            'cmi.objectives._count': 0,
            'cmi.interactions._count': 0,
            'cmi.learner_name': self.request.user.get_full_name(),
            'cmi.learner_id': self.request.user.username,
            'cmi.location': '',
            'cmi.score.raw': 0,
            'cmi.score.scaled': 0,
            'cmi.score.min': 0,
            'cmi.score.max': 0,
            'cmi.total_time': 0,
            'cmi.completion_status': attempt.completion_status,
            'cmi.success_status': ''
        }
        # TODO only get the latest values of elements, somehow

        latest_elements = {}

        for e in attempt.scormelements.all().order_by('time'):
            latest_elements[e.key] = e.value

        scorm_cmi.update(latest_elements)
        
        context['scorm_cmi'] = json.dumps(scorm_cmi)

        return context
