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
from django.http import StreamingHttpResponse
from django.utils.translation import ugettext_lazy as _, ugettext
from itertools import groupby
from channels import Channel
import datetime
import csv
import json

patch_reverse()

from functools import wraps

from .models import LTIConsumer, LTIUserData, Resource, AccessToken, Exam, Attempt, ScormElement, ReportProcess
from .forms import ResourceSettingsForm

# Create your views here.
@csrf_exempt
def index(request):
    context = {
        'entry_url': request.build_absolute_uri(reverse('lti_entry',exclude_resource_link_id=True)),
    }
    return render(request,'numbas_lti/index.html',context)

def request_is_instructor(request):
    return 'Instructor' in request.LTI.get('roles')

@csrf_exempt
def no_resource(request):
    return render(request,'numbas_lti/error_no_resource.html',{})

@csrf_exempt
def lti_entry(request):

    try:
        request.resource
    except AttributeError:
        return no_resource(request)

    client_key = request.POST.get('oauth_consumer_key')
    consumer = LTIConsumer.objects.get(key=client_key)
    print("Client key: {}\nConsumer: {}".format(client_key,consumer))

    user_data,_ = LTIUserData.objects.get_or_create(
        user=request.user,
        resource=request.resource,
        consumer=consumer,
        consumer_user_id = request.LTI.get('user_id')
    )
    user_data.lis_result_sourcedid = request.POST.get('lis_result_sourcedid')
    user_data.lis_outcome_service_url = request.POST.get('lis_outcome_service_url')
    user_data.save()

    if request_is_instructor(request):
        if not request.resource.exam:
            return redirect(reverse('create_exam'))
        else:
            return redirect(reverse('dashboard',args=(request.resource.pk,)))
    else:
        if not request.resource.exam:
            return render(request,'numbas_lti/exam_not_set_up.html',{})
        else:
            return redirect(reverse('show_attempts'))

class MustBeInstructorMixin(LTIRoleRestrictionMixin):
    allowed_roles = ['Instructor']

class ManagementViewMixin(object):
    context_object_name = 'resource'

    def get_context_data(self,*args,**kwargs):
        context = super(ManagementViewMixin,self).get_context_data(*args,**kwargs)
        context.update({
            'management_tab': self.management_tab
        })
        return context

class CreateExamView(MustBeInstructorMixin,generic.edit.CreateView):
    model = Exam
    fields = ['package']
    template_name = 'numbas_lti/management/create_exam.html'

    def form_valid(self,form):
        self.object = form.save()
        self.request.resource.exam = self.object
        self.request.resource.save()
        return http.HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse('dashboard',args=(self.request.resource.pk,))

class ReplaceExamView(ManagementViewMixin,CreateExamView):
    management_tab = 'settings'
    template_name = 'numbas_lti/management/replace_exam.html'

class DashboardView(ManagementViewMixin,MustBeInstructorMixin,generic.detail.DetailView):
    model = Resource
    template_name = 'numbas_lti/management/dashboard.html'
    management_tab = 'dashboard'

    def get_context_data(self,*args,**kwargs):
        context = super(DashboardView,self).get_context_data(*args,**kwargs)

        resource = self.get_object()

        context['students'] = User.objects.filter(attempts__resource=resource).distinct()
        last_report_process = resource.report_processes.first()
        if last_report_process and (not last_report_process.dismissed):
            context['last_report_process'] = last_report_process

        context['student_summary'] = [
            (
                student,
                resource.grade_user(student),
                student.lti_data.get(resource=resource),
                Attempt.objects.filter(user=student,resource=resource).count(),
                AccessToken.objects.filter(user=student,resource=resource).count(),
            ) 
            for student in resource.students().all()
        ]

        return context

class AllAttemptsView(ManagementViewMixin,MustBeInstructorMixin,generic.detail.DetailView):
    model = Resource
    template_name = 'numbas_lti/management/attempts.html'
    management_tab = 'attempts'

class ResourceSettingsView(ManagementViewMixin,MustBeInstructorMixin,generic.edit.UpdateView):
    model = Resource
    form_class = ResourceSettingsForm
    template_name = 'numbas_lti/management/resource_settings.html'
    context_object_name = 'resource'
    management_tab = 'settings'

    def get_success_url(self):
        return reverse('dashboard',args=(self.get_object().pk,))

class EchoFile(object):
    def write(self,value):
        return value

class CSVView(object):
    def get_rows(self):
        raise NotImplementedError()
    def get_filename(self):
        raise NotImplementedError()

    def render_to_response(self,context):
        buffer = EchoFile()
        writer = csv.writer(buffer)
        rows = self.get_rows()
        response = StreamingHttpResponse((writer.writerow(row) for row in rows),content_type="text/csv")
        response['Content-Disposition'] = 'attachment; filename="{}"'.format(self.get_filename())
        return response

class ScoresCSV(MustBeInstructorMixin,CSVView,generic.detail.DetailView):
    model = Resource
    def get_rows(self):
        headers = [_(x) for x in ['First name','Last name','Email','Username','Percentage']]
        yield headers

        resource = self.object
        for student in resource.students().all():
            user_data = LTIUserData.objects.get(resource=resource,user=student)
            yield (
                student.first_name,
                student.last_name,
                student.email,
                user_data.consumer_user_id,
                resource.grade_user(student)*100
            )

    def get_filename(self):
        return _("{slug}-scores.csv").format(slug=self.object.slug)

class AttemptsCSV(MustBeInstructorMixin,CSVView,generic.detail.DetailView):
    model = Resource
    def get_rows(self):
        resource = self.object
        num_questions = resource.num_questions()

        headers = [_(x) for x in ['First name','Last name','Email','Username','Start time','Completed?','Total score','Percentage']]+[_('Question {n}').format(n=i+1) for i in range(num_questions)]
        yield headers

        for attempt in resource.attempts.all():
            user_data = LTIUserData.objects.get(resource=resource,user=attempt.user)
            row = [
                attempt.user.first_name,
                attempt.user.last_name,
                attempt.user.email,
                user_data.consumer_user_id,
                attempt.start_time,
                attempt.completion_status,
                attempt.raw_score,
                attempt.scaled_score*100,
            ]+[attempt.question_score(n) for n in range(num_questions)]
            yield row

    def get_filename(self):
        return _("{slug}-attempts.csv").format(slug=self.object.slug)

class AttemptSCORMListing(MustBeInstructorMixin,ManagementViewMixin,generic.detail.DetailView):
    model = Attempt
    management_tab = 'attempts'
    template_name = 'numbas_lti/management/attempt_scorm_listing.html'
    context_object_name = 'attempt'

    def get_context_data(self,*args,**kwargs):
        context = super(AttemptSCORMListing,self).get_context_data(*args,**kwargs)

        context['keys'] = [(x,list(y)) for x,y in groupby(self.object.scormelements.order_by('key','-time'),key=lambda x:x.key)]
        context['show_stale_elements'] = True

        return context

class ReportAllScoresView(MustBeInstructorMixin,ManagementViewMixin,generic.detail.DetailView):
    model = Resource
    management_tab = 'dashboard'
    template_name = 'numbas_lti/management/report_all_scores.html'
    context_object_name = 'resource'

    def get(self,*args,**kwargs):
        Channel("report.all_scores").send({'pk':self.get_object().pk})
        return super(ReportAllScoresView,self).get(*args,**kwargs)

@lti_role_required(['Instructor'])
def grant_access_token(request,user_id):
    user = User.objects.get(id=user_id)
    AccessToken.objects.create(user=user,resource=request.resource)

    return redirect(reverse('dashboard',args=(request.resource.pk,)))

@lti_role_required(['Instructor'])
def remove_access_token(request,user_id):
    user = User.objects.get(id=user_id)
    AccessToken.objects.filter(user=user,resource=request.resource).first().delete()

    return redirect(reverse('dashboard',args=(request.resource.pk,)))

class DismissReportProcessView(MustBeInstructorMixin,generic.detail.DetailView):
    model = ReportProcess

    def render_to_response(self,context):
        process = self.get_object()
        process.dismissed = True
        process.save()
        return redirect(reverse('dashboard',args=(process.resource.pk,)))

class DeleteAttemptView(MustBeInstructorMixin,ManagementViewMixin,generic.edit.DeleteView):
    model = Attempt
    context_object_name = 'attempt'
    management_tab = 'attempts'
    template_name = 'numbas_lti/management/delete_attempt.html'

    def delete(self,request,*args,**kwargs):
        self.object = self.get_object()
        self.object.deleted = True
        self.object.save()
        return http.HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse('manage_attempts',args=(self.request.resource.pk,))

class RunExamView(MustBeInstructorMixin,ManagementViewMixin,generic.detail.DetailView):
    """
        Run an exam without saving any attempt data
    """
    management_tab = 'test_run'
    model = Exam
    template_name = 'numbas_lti/management/run_exam.html'
    context_object_name = 'exam'

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
        raise PermissionDenied(ugettext("You can't start a new attempt at this exam"))

    if Attempt.objects.filter(resource=request.resource,user=request.user).count() == request.resource.max_attempts > 0:
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
                raise PermissionDenied(ugettext("You're not allowed to review this attempt."))

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

