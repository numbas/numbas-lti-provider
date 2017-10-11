from django.conf import settings
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth import login, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.mixins import PermissionRequiredMixin, LoginRequiredMixin
from django.shortcuts import render,redirect
from django.utils.decorators import available_attrs
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django_auth_lti.decorators import lti_role_required
from django_auth_lti.const import LEARNER, INSTRUCTOR
from django_auth_lti.patch_reverse import patch_reverse
from django_auth_lti.mixins import LTIRoleRestrictionMixin
from django.views import generic
from django.core.urlresolvers import reverse, reverse_lazy
from django.core.exceptions import PermissionDenied
from django import http
from django.http import StreamingHttpResponse, JsonResponse
from django.utils.translation import ugettext_lazy as _, ugettext
from django.template.loader import get_template
from django.contrib import messages
from django.forms.models import inlineformset_factory
from django.db.models import Q
from itertools import groupby
from channels import Channel
import datetime
from django.utils import timezone
import csv
import json
import simplejson
import string
from django.contrib.staticfiles.templatetags.staticfiles import static
import requests

patch_reverse()

from functools import wraps

from .models import LTIConsumer, LTIUserData, Resource, AccessToken, Exam, Attempt, ScormElement, ReportProcess, RemarkPart, DiscountPart, EditorLink, EditorLinkProject
from . import forms

def get_lti_entry_url(request):
    return request.build_absolute_uri(reverse('lti_entry',exclude_resource_link_id=True))

def get_config_url(request):
    return request.build_absolute_uri(reverse('config_xml',exclude_resource_link_id=True))

@csrf_exempt
def index(request):
    if not User.objects.filter(is_superuser=True).exists():
        return redirect(reverse('create_superuser'))
    context = {
        'entry_url': get_lti_entry_url(request),
    }
    return render(request,'numbas_lti/index.html',context)

def request_is_instructor(request):
    if request.user.is_superuser:
        return True
    return 'Instructor' in request.LTI.get('roles')

@csrf_exempt
def no_resource(request):
    return render(request,'numbas_lti/error_no_resource.html',{'debug':settings.DEBUG, 'post_data': sorted(request.POST.items(),key=lambda x:x[0])})

def static_view(template_name):
    return generic.TemplateView.as_view(template_name=template_name)

no_websockets = static_view('numbas_lti/no_websockets.html')
not_authorized = static_view('numbas_lti/not_authorized.html')

@csrf_exempt
def config_xml(request):
    return render(request,
        'numbas_lti/config.xml',
        {
            'entry_url': get_lti_entry_url(request),
            'icon': request.build_absolute_uri(static('icon.png')),
        }, 
        content_type='application/xml' 
    )

@csrf_exempt
def lti_entry(request):

    try:
        request.resource
    except AttributeError:
        return no_resource(request)

    client_key = request.POST.get('oauth_consumer_key')
    consumer = LTIConsumer.objects.get(key=client_key)

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
            return redirect(reverse('create_exam',args=(request.resource.pk,)))
        else:
            return redirect(reverse('dashboard',args=(request.resource.pk,)))
    else:
        if not request.resource.exam:
            return render(request,'numbas_lti/exam_not_set_up.html',{})
        else:
            return redirect(reverse('show_attempts'))

class LTIRoleOrSuperuserMixin(LTIRoleRestrictionMixin):
    def check_allowed(self, request):
        if request.user.is_superuser:
            return True
        else:
            return super(LTIRoleOrSuperuserMixin, self).check_allowed(request)

class MustBeInstructorMixin(LTIRoleOrSuperuserMixin):
    allowed_roles = ['Instructor']

class ManagementViewMixin(object):
    def get_context_data(self,*args,**kwargs):
        context = super(ManagementViewMixin,self).get_context_data(*args,**kwargs)
        context.update({
            'management_tab': self.management_tab
        })
        return context

class ResourceManagementViewMixin(ManagementViewMixin):
    context_object_name = 'resource'
    resource_pk_url_kwarg = 'pk'

    def get_resource(self):
        if self.model == Resource:
            return self.get_object()
        else:
            pk = self.kwargs.get(self.resource_pk_url_kwarg)
            return Resource.objects.get(pk=pk)

    def dispatch(self,*args,**kwargs):
        self.resource = self.get_resource()
        if not hasattr(self.request,'resource') or self.request.resource is None:
            self.request.resource = self.resource

        return super(ResourceManagementViewMixin,self).dispatch(*args,**kwargs)

class MustHaveExamMixin(object):
    def dispatch(self,*args,**kwargs):
        resource = self.get_resource()
        if resource.exam is None:
            return redirect(reverse('create_exam',args=(resource.pk,)))

        return super(MustHaveExamMixin,self).dispatch(*args,**kwargs)

class CreateSuperuserView(generic.edit.CreateView):
    model = User
    form_class = forms.CreateSuperuserForm
    template_name = 'numbas_lti/management/create_superuser.html'

    def form_valid(self,form):
        self.object = form.save()
        user = authenticate(username=self.object.username,password=form.cleaned_data['password1'])
        login(self.request,user)
        return redirect(self.get_success_url())

    def dispatch(self,request,*args,**kwargs):
        if User.objects.filter(is_superuser=True).exists():
            return redirect(reverse('index'))
        else:
            return super(CreateSuperuserView,self).dispatch(request,*args,**kwargs)

    def get_success_url(self):
        if LTIConsumer.objects.exists():
            return reverse('list_consumers')
        else:
            return reverse('create_consumer')

class CreateExamView(ResourceManagementViewMixin,MustBeInstructorMixin,generic.edit.CreateView):
    model = Exam
    management_tab = 'create_exam'
    template_name = 'numbas_lti/management/create_exam.html'
    form_class = forms.CreateExamForm

    def get_context_data(self,*args,**kwargs):
        context = super(CreateExamView,self).get_context_data(*args,**kwargs)

        context['editor_links'] = EditorLink.objects.all()
        available_exams = []
        for el in EditorLink.objects.all():
            available_exams += el.available_exams
        context['exams'] = available_exams

        return context

    def form_valid(self,form):
        self.object = form.save()
        self.request.resource.exam = self.object
        self.request.resource.save()
        return http.HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse('dashboard',args=(self.request.resource.pk,))

class ReplaceExamView(CreateExamView):
    management_tab = 'settings'
    template_name = 'numbas_lti/management/replace_exam.html'

    def get_context_data(self,*args,**kwargs):
        context = super(ReplaceExamView,self).get_context_data(*args,**kwargs)
        context['current_exam'] = self.request.resource.exam

        return context

    def form_valid(self,form):
        response = super(CreateExamView,self).form_valid(form)

        messages.add_message(self.request,messages.INFO,_('The exam package has been updated.'))

        return response

class DashboardView(MustHaveExamMixin,ResourceManagementViewMixin,MustBeInstructorMixin,generic.detail.DetailView):
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
                student.lti_data.filter(resource=resource).last(),
                Attempt.objects.filter(user=student,resource=resource).exclude(broken=True).count(),
                AccessToken.objects.filter(user=student,resource=resource).count(),
            ) 
            for student in resource.students().all()
        ]

        return context

class DiscountPartsView(MustHaveExamMixin,ResourceManagementViewMixin,MustBeInstructorMixin,generic.detail.DetailView):
    model = Resource
    template_name = 'numbas_lti/management/discount.html'
    context_object_name = 'resource'
    management_tab = 'dashboard'

    def get_context_data(self,*args,**kwargs):
        context = super(DiscountPartsView,self).get_context_data(*args,**kwargs)

        resource = self.get_object()
        hierarchy = resource.part_hierarchy()
        out = []
        fst = lambda x:x[0]

        def row(q,p=None,g=None):
            qnum = int(q)+1
            path = 'q{}'.format(q)
            if p is not None:
                pletter = string.ascii_lowercase[int(p)]
                path += 'p{}'.format(p)
                if g is not None:
                    path += 'g{}'.format(g)
            else:
                pletter = None

            out = {
                'q': qnum,
                'p': pletter,
                'g': g,
                'path': path,
            }
            if p is not None:
                discount = DiscountPart.objects.filter(resource=resource,part=path).first()
                out.update({
                    'discount': discount,
                    'form': forms.DiscountPartBehaviourForm(instance=discount)
                })

            return out

        for i,q in sorted(hierarchy.items(),key=fst):
            qnum = int(i)+1
            out.append(row(i))

            for j,p in sorted(q.items(),key=fst):
                out.append(row(i,j))

                for g in p['gaps']:
                    out.append(row(i,j,g))
        
        context['parts'] = out

        return context

class DiscountPartView(MustBeInstructorMixin,generic.base.View):

    def post(self,request,pk,*args,**kwargs):
        resource = Resource.objects.get(pk=pk)
        part = request.POST['part']
        discount,created = DiscountPart.objects.get_or_create(resource=resource,part=part)
        template = get_template('numbas_lti/management/discount/discounted.html')
        html = template.render({'resource':resource,'discount':discount,'form':forms.DiscountPartBehaviourForm(instance=discount)})
        return JsonResponse({'pk':discount.pk,'created':created, 'behaviour': discount.behaviour, 'html':html})

class DiscountPartDeleteView(MustBeInstructorMixin,generic.edit.DeleteView):
    model = DiscountPart

    def delete(self,*args,**kwargs):
        discount = self.get_object()
        discount.delete()

        resource = discount.resource
        template = get_template('numbas_lti/management/discount/not_discounted.html')
        html = template.render({'resource':resource})
        return JsonResponse({'html':html})

class DiscountPartUpdateView(MustBeInstructorMixin,generic.edit.UpdateView):
    model = DiscountPart
    form_class = forms.DiscountPartBehaviourForm

    def form_valid(self,form,*args,**kwargs):
        self.object = form.save()
        return JsonResponse({})

class RemarkPartsView(MustHaveExamMixin,ResourceManagementViewMixin,MustBeInstructorMixin,generic.detail.DetailView):
    model = Attempt
    template_name = 'numbas_lti/management/remark.html'
    context_object_name = 'attempt'
    management_tab = 'attempts'

    def get_context_data(self,*args,**kwargs):
        context = super(RemarkPartsView,self).get_context_data(*args,**kwargs)

        attempt = self.get_object()
        hierarchy = attempt.part_hierarchy()
        out = []
        fst = lambda x:x[0]

        def row(q,p=None,g=None,parent=None,has_gaps=False):
            qnum = int(q)+1
            path = 'q{}'.format(q)
            if p is not None:
                pletter = string.ascii_lowercase[int(p)]
                path += 'p{}'.format(p)
                if g is not None:
                    path += 'g{}'.format(g)
            else:
                pletter = None

            remark = RemarkPart.objects.filter(attempt=attempt,part=path).first()
            out = {
                'q': qnum,
                'p': pletter,
                'g': g,
                'path': path,
            }
            if parent is not None and parent['discount'] is not None:
                discount = parent['discount']
            else:
                discount = attempt.part_discount(path)

            if p is not None:
                out.update({
                    'score': attempt.part_score(path),
                    'max_score': attempt.part_max_score(path),
                    'discount': discount,
                    'remark': remark,
                    'parent_remarked': parent is not None and parent['remark'] is not None,
                    'form': forms.RemarkPartScoreForm(instance=remark),
                    'has_gaps': has_gaps
                })

            return out

        for i,q in sorted(hierarchy.items(),key=fst):
            qnum = int(i)+1
            out.append(row(i))

            for j,p in sorted(q.items(),key=fst):
                has_gaps = len(p['gaps'])>0
                prow = row(i,j,has_gaps=has_gaps)
                out.append(prow)

                for g in p['gaps']:
                    out.append(row(i,j,g,prow))

        context['parts'] = out

        return context

class RemarkPartView(MustBeInstructorMixin,generic.base.View):

    def post(self,request,pk,*args,**kwargs):
        attempt = Attempt.objects.get(pk=pk)
        part = request.POST['part']

        remark,created = RemarkPart.objects.get_or_create(attempt=attempt,part=part,score=attempt.part_score(part))

        template = get_template('numbas_lti/management/remark/remarked.html')
        html = template.render({
            'attempt':attempt,
            'remark':remark,
            'form':forms.RemarkPartScoreForm(instance=remark),
            'max_score': remark.attempt.part_max_score(part),
        })

        return JsonResponse({
            'pk':remark.pk,
            'created':created, 
            'score': remark.score, 
            'html':html
        })

class RemarkPartDeleteView(MustBeInstructorMixin,generic.edit.DeleteView):
    model = RemarkPart

    def delete(self,*args,**kwargs):
        remark = self.get_object()
        remark.delete()

        attempt = remark.attempt
        template = get_template('numbas_lti/management/remark/not_remarked.html')
        html = template.render({
            'attempt':attempt,
            'score':attempt.part_score(remark.part),
            'max_score':attempt.part_max_score(remark.part),
            'path':remark.part,
        })
        return JsonResponse({'html':html})

class RemarkPartUpdateView(MustBeInstructorMixin,generic.edit.UpdateView):
    model = RemarkPart
    form_class = forms.RemarkPartScoreForm

    def form_valid(self,form,*args,**kwargs):
        self.object = form.save()
        return JsonResponse({})


class ReopenAttemptView(MustBeInstructorMixin,generic.detail.DetailView):
    model = Attempt

    def get(self, request, *args, **kwargs):
        attempt = self.get_object()
        e = ScormElement.objects.create(
                attempt=attempt,
                key='cmi.completion_status',
                value='incomplete',
                time=timezone.make_aware(datetime.datetime.now()),
                counter=1
            )
        messages.add_message(self.request,messages.SUCCESS,_('{}\'s attempt has been reopened.'.format(attempt.user.get_full_name())))
        return redirect(reverse('manage_attempts',args=(attempt.resource.pk,)))

class AllAttemptsView(MustHaveExamMixin,ResourceManagementViewMixin,MustBeInstructorMixin,generic.ListView):
    model = Attempt
    template_name = 'numbas_lti/management/attempts.html'
    management_tab = 'attempts'
    paginate_by = 20
    context_object_name = 'attempts'

    def get_queryset(self, *args, **kwargs):
        resource = self.get_resource()
        attempts = resource.attempts.all()
        if 'query' in self.request.GET:
            query = self.request.GET.get('query')
            for word in query.split():
                print(word)
                attempts = attempts.filter(Q(user__first_name__icontains=word) | Q(user__last_name__icontains=word))
        return attempts

    def get_resource(self):
        return Resource.objects.get(pk=self.kwargs.get('pk'))

    def get_context_data(self, *args, **kwargs):
        context = super(AllAttemptsView,self).get_context_data(*args,**kwargs)
        resource = self.get_resource()
        context['resource'] = resource

        return context

class ResourceSettingsView(MustHaveExamMixin,ResourceManagementViewMixin,MustBeInstructorMixin,generic.edit.UpdateView):
    model = Resource
    form_class = forms.ResourceSettingsForm
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
            user_data = resource.user_data(student)
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
        num_questions = resource.num_questions

        headers = [_(x) for x in ['First name','Last name','Email','Username','Start time','Completed?','Total score','Percentage']]+[_('Question {n}').format(n=i+1) for i in range(num_questions)]
        yield headers

        for attempt in resource.attempts.all():
            user_data = resource.user_data(attempt.user)
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

class AttemptSCORMListing(MustHaveExamMixin,MustBeInstructorMixin,ResourceManagementViewMixin,generic.detail.DetailView):
    model = Attempt
    management_tab = 'attempts'
    template_name = 'numbas_lti/management/attempt_scorm_listing.html'
    context_object_name = 'attempt'

    def get_resource(self):
        return self.get_object().resource

    def get_context_data(self,*args,**kwargs):
        context = super(AttemptSCORMListing,self).get_context_data(*args,**kwargs)

        context['keys'] = [(x,list(y)) for x,y in groupby(self.object.scormelements.order_by('key','-time','-counter'),key=lambda x:x.key)]
        context['show_stale_elements'] = True

        return context

class ReportAllScoresView(MustHaveExamMixin,MustBeInstructorMixin,ResourceManagementViewMixin,generic.detail.DetailView):
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

class DeleteAttemptView(MustHaveExamMixin,MustBeInstructorMixin,ResourceManagementViewMixin,generic.edit.DeleteView):
    model = Attempt
    context_object_name = 'attempt'
    management_tab = 'attempts'
    template_name = 'numbas_lti/management/delete_attempt.html'

    def get_resource(self):
        return self.get_object().resource

    def delete(self,request,*args,**kwargs):
        self.object = self.get_object()
        self.object.deleted = True
        self.object.save()
        return http.HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse('manage_attempts',args=(self.request.resource.pk,))

class RunExamView(MustHaveExamMixin,MustBeInstructorMixin,ResourceManagementViewMixin,generic.detail.DetailView):
    """
        Run an exam without saving any attempt data
    """
    management_tab = 'test_run'
    model = Exam
    template_name = 'numbas_lti/management/run_exam.html'
    context_object_name = 'exam'

    def get_resource(self):
        return Resource.objects.filter(exam=self.get_object()).first()

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
        return Attempt.objects.filter(resource=self.request.resource,user=self.request.user).exclude(broken=True)

    def dispatch(self,request,*args,**kwargs):
        if not self.get_queryset().exists():
            return new_attempt(request)
        else:
            return super(ShowAttemptsView,self).dispatch(request,*args,**kwargs)

    def get_context_data(self,*args,**kwargs):
        context = super(ShowAttemptsView,self).get_context_data(*args,**kwargs)

        context['resource'] = self.request.resource
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

        if attempt.completion_status=='not attempted':
            entry = 'ab-initio'
        elif attempt.scormelements.filter(key='cmi.suspend_data').exists():
            entry = 'resume'
        else:
            # Not enough data was saved last time. Mark this attempt as broken, and create a new one.
            # This isn't ideal, because what's happening isn't made clear to the student, but this should only occur when the student didn't really start the attempt they're resuming
            broken_attempt = attempt
            broken_attempt.broken = True
            broken_attempt.save()

            context['attempt'] = attempt
            attempt = Attempt.objects.create(
                resource = broken_attempt.resource,
                exam = broken_attempt.exam,
                user = broken_attempt.user
            )
            entry = 'ab-initio'


        if attempt.completion_status=='completed':
            mode = 'review'
        else:
            mode = 'normal'

        if attempt.user != self.request.user:
            if request_is_instructor(self.request):
                mode = 'review'
            else:
                raise PermissionDenied(ugettext("You're not allowed to review this attempt."))

        context['mode'] = mode

        user = attempt.user
        user_data = attempt.resource.user_data(user)

        scorm_cmi = {
            'cmi.suspend_data': '',
            'cmi.objectives._count': 0,
            'cmi.interactions._count': 0,
            'cmi.learner_name': user.get_full_name(),
            'cmi.learner_id': user_data.consumer_user_id,
            'cmi.location': '',
            'cmi.score.raw': 0,
            'cmi.score.scaled': 0,
            'cmi.score.min': 0,
            'cmi.score.max': 0,
            'cmi.total_time': 0,
            'cmi.success_status': '',
            'cmi.completion_status': attempt.completion_status,
        }
        scorm_cmi = {k: {'value':v,'time':attempt.start_time.timestamp()} for k,v in scorm_cmi.items()}

        # TODO only fetch the latest values of elements from the DB, somehow

        latest_elements = {}

        for e in attempt.scormelements.all().order_by('time','counter'):
            latest_elements[e.key] = {'value':e.value,'time':e.time.timestamp()}

        scorm_cmi.update(latest_elements)

        dynamic_cmi = {
            'cmi.mode': mode,
            'cmi.entry': entry,
        }
        now = datetime.datetime.now().timestamp()
        dynamic_cmi = {k: {'value':v,'time':now} for k,v in dynamic_cmi.items()}
        scorm_cmi.update(dynamic_cmi)
        
        context['scorm_cmi'] = simplejson.encoder.JSONEncoderForHTML().encode(scorm_cmi)

        return context

@require_POST
def scorm_data_fallback(request,pk,*args,**kwargs):
    """ An AJAX fallback to save SCORM data, when the websocket fails """
    attempt = Attempt.objects.get(pk=pk)
    batches = json.loads(request.body.decode())
    done = []
    for id,elements in batches.items():
        for element in elements:
            ScormElement.objects.create(
                attempt = attempt,
                key = element['key'], 
                value = element['value'],
                time = timezone.make_aware(datetime.datetime.fromtimestamp(element['time'])),
                counter = element.get('counter',0)
            )
        done.append(id)
    return JsonResponse({'received_batches':done})

class ConsumerManagementMixin(PermissionRequiredMixin,LoginRequiredMixin,ManagementViewMixin):
    permission_required = ('numbas_lti.add_lticonsumer',)
    login_url = reverse_lazy('login')
    management_tab = 'consumers'

class ListConsumersView(ConsumerManagementMixin,generic.list.ListView):
    model = LTIConsumer
    template_name = 'numbas_lti/management/admin/list_consumers.html'

    def get_context_data(self,*args,**kwargs):
        context = super(ListConsumersView,self).get_context_data(*args,**kwargs)
        context['entry_url'] = get_lti_entry_url(self.request)
        context['config_url'] = get_config_url(self.request)
        context['icon_url'] = self.request.build_absolute_uri(static('icon.png'))

        return context

class CreateConsumerView(ConsumerManagementMixin,generic.edit.CreateView):
    model = LTIConsumer
    template_name = 'numbas_lti/management/admin/create_consumer.html'
    form_class = forms.CreateConsumerForm
    success_url = reverse_lazy('list_consumers')

class DeleteConsumerView(ConsumerManagementMixin,generic.edit.DeleteView):
    model = LTIConsumer
    context_object_name = 'consumer'
    template_name = 'numbas_lti/management/admin/confirm_delete_consumer.html'
    success_url = reverse_lazy('list_consumers')

    def form_valid(self,form):
        consumer = self.get_object()
        consumer.deleted = True
        consumer.save()

        return redirect(self.get_success_url())

class ManageConsumerView(ConsumerManagementMixin,generic.detail.DetailView):
    model = LTIConsumer
    context_object_name = 'consumer'
    template_name = 'numbas_lti/management/admin/view_consumer.html'

    def get_context_data(self, *args, **kwargs):
        context = super(ManageConsumerView,self).get_context_data(*args,**kwargs)
        
        consumer = self.get_object()
        context['unnamed_contexts'] = consumer.contexts.filter(name='').all()
        context['named_contexts'] = consumer.contexts.exclude(name='').all()

        return context

class EditorLinkManagementMixin(PermissionRequiredMixin,LoginRequiredMixin,ManagementViewMixin):
    permission_required = ('numbas_lti.add_editorlink',)
    management_tab = 'editor-links'
    login_url = reverse_lazy('login')

class ListEditorLinksView(EditorLinkManagementMixin,generic.list.ListView):
    model = EditorLink
    template_name = 'numbas_lti/management/admin/list_editorlinks.html'

class UpdateEditorLinkView(EditorLinkManagementMixin,generic.edit.UpdateView):
    template_name = 'numbas_lti/management/admin/edit_editorlink.html'
    model = EditorLink
    fields = ['name']
    success_url = reverse_lazy('list_editorlinks')

    def projectformset(self,*args,**kwargs):
        if 'initial' in kwargs:
            extra = len(kwargs['initial'])
        else:
            extra = 0
        factory = inlineformset_factory(
            EditorLink,
            EditorLinkProject,
            form=forms.EditorLinkProjectForm,
            can_delete=False,
            extra=extra
        )
        return factory(*args,**kwargs)

    def get_context_data(self,*args,**kwargs):
        context = super(UpdateEditorLinkView,self).get_context_data(*args,**kwargs)

        if 'project_form' not in kwargs:
            selected_projects = [p.remote_id for p in self.object.projects.all()]

            projects_data = requests.get('{}/api/projects'.format(self.object.url)).json()
            projects = []
            for p in projects_data:
                projects.append({
                    'name': p['name'],
                    'description': p['description'],
                    'remote_id': p['pk'],
                    'homepage': p['homepage'],
                    'rest_url': p['url'],
                    'use': p['pk'] in selected_projects,
                })

            context['project_form'] = self.projectformset(initial=projects)

        return context

    def post(self,request,*args,**kwargs):
        self.object = self.get_object()
        project_form = self.projectformset(self.request.POST)
        form = self.get_form()
        if project_form.is_valid():
            return self.form_valid(form,project_form)
        else:
            return self.form_invalid(form,project_form)

    def form_valid(self,form,project_form):
        form.save()
        self.object.projects.all().delete()
        for pform in project_form:
            if pform.cleaned_data['use']:
                pform.instance.editor = self.object
                link = pform.save()
        Channel("editorlink.update_cache").send({'pk':self.object.pk,'bounce':False})

        return http.HttpResponseRedirect(self.get_success_url())

    def form_invalid(self,form,project_form):
        return self.render_to_response(self.get_context_data(form=form,project_form=project_form))

class CreateEditorLinkView(EditorLinkManagementMixin,generic.edit.CreateView):
    model = EditorLink
    form_class = forms.CreateEditorLinkForm
    template_name = 'numbas_lti/management/admin/create_editorlink.html'

    def form_valid(self,form):
        editorlink = self.object = form.save()
        messages.add_message(self.request,messages.SUCCESS,_('Connected to {} at {}.'.format(editorlink.name,editorlink.url)))
        return http.HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse('edit_editorlink',args=(self.object.pk,))

class DeleteEditorLinkView(EditorLinkManagementMixin,generic.edit.DeleteView):
    model = EditorLink
    template_name = 'numbas_lti/management/admin/confirm_delete_editorlink.html'
    success_url = reverse_lazy('list_editorlinks')
    context_object_name = 'editorlink'

    def delete(self,request,*args,**kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        self.object.delete()
        messages.add_message(self.request,messages.SUCCESS,_('The connection to {} has been deleted.'.format(self.object.name)))
        return http.HttpResponseRedirect(success_url)
