from django.contrib.auth import login, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.mixins import PermissionRequiredMixin, LoginRequiredMixin
from django.shortcuts import render,redirect
from django.utils.decorators import available_attrs
from django.views.decorators.csrf import csrf_exempt
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
from itertools import groupby
from channels import Channel
import datetime
import csv
import json
import string

patch_reverse()

from functools import wraps

from .models import LTIConsumer, LTIUserData, Resource, AccessToken, Exam, Attempt, ScormElement, ReportProcess, RemarkPart, DiscountPart
from .forms import ResourceSettingsForm, DiscountPartBehaviourForm, RemarkPartScoreForm, CreateSuperuserForm, CreateConsumerForm

def get_lti_entry_url(request):
    return request.build_absolute_uri(reverse('lti_entry',exclude_resource_link_id=True))

@csrf_exempt
def index(request):
    if not User.objects.filter(is_superuser=True).exists():
        return redirect(reverse('create_superuser'))
    context = {
        'entry_url': get_lti_entry_url(request),
    }
    return render(request,'numbas_lti/index.html',context)

def request_is_instructor(request):
    return 'Instructor' in request.LTI.get('roles')

@csrf_exempt
def no_resource(request):
    return render(request,'numbas_lti/error_no_resource.html',{})

def static_view(template_name):
    return generic.TemplateView.as_view(template_name=template_name)

no_websockets = static_view('numbas_lti/no_websockets.html')
not_authorized = static_view('numbas_lti/not_authorized.html')

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

class CreateSuperuserView(generic.edit.CreateView):
    model = User
    form_class = CreateSuperuserForm
    template_name = 'numbas_lti/management/create_superuser.html'

    def form_valid(self,form):
        self.object = form.save()
        user = authenticate(username=self.object.username,password=form.cleaned_data['password1'])
        print(user)
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
                student.lti_data.filter(resource=resource).last(),
                Attempt.objects.filter(user=student,resource=resource).exclude(broken=True).count(),
                AccessToken.objects.filter(user=student,resource=resource).count(),
            ) 
            for student in resource.students().all()
        ]

        return context

class DiscountPartsView(ManagementViewMixin,MustBeInstructorMixin,generic.detail.DetailView):
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
                    'form': DiscountPartBehaviourForm(instance=discount)
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
        html = template.render({'resource':resource,'discount':discount,'form':DiscountPartBehaviourForm(instance=discount)})
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
    form_class = DiscountPartBehaviourForm

    def form_valid(self,form,*args,**kwargs):
        self.object = form.save()
        return JsonResponse({})

class RemarkPartsView(ManagementViewMixin,MustBeInstructorMixin,generic.detail.DetailView):
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
                    'form': RemarkPartScoreForm(instance=remark),
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
            'form':RemarkPartScoreForm(instance=remark),
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
    form_class = RemarkPartScoreForm

    def form_valid(self,form,*args,**kwargs):
        self.object = form.save()
        return JsonResponse({})


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
        num_questions = resource.num_questions()

        headers = [_(x) for x in ['First name','Last name','Email','Username','Start time','Completed?','Total score','Percentage']]+[_('Question {n}').format(n=i+1) for i in range(num_questions)]
        yield headers

        for attempt in resource.attempts.all():
            user_data = resource.use_data(attempt.user)
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
            'cmi.mode': mode,
            'cmi.entry': entry,
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
            'cmi.completion_status': attempt.completion_status,
            'cmi.success_status': ''
        }

        # TODO only fetch the latest values of elements from the DB, somehow

        latest_elements = {}

        for e in attempt.scormelements.all().order_by('time'):
            latest_elements[e.key] = e.value

        scorm_cmi.update(latest_elements)
        
        context['scorm_cmi'] = json.dumps(scorm_cmi)

        return context

class ConsumerManagementMixin(PermissionRequiredMixin,LoginRequiredMixin):
    permission_required = ('numbas_lti.add_consumer',)
    login_url = reverse_lazy('login')

class ListConsumersView(ConsumerManagementMixin,generic.list.ListView):
    model = LTIConsumer
    template_name = 'numbas_lti/management/list_consumers.html'

    def get_context_data(self,*args,**kwargs):
        context = super(ListConsumersView,self).get_context_data(*args,**kwargs)
        context['entry_url'] = get_lti_entry_url(self.request)
        return context

class CreateConsumerView(ConsumerManagementMixin,generic.edit.CreateView):
    model = LTIConsumer
    template_name = 'numbas_lti/management/create_consumer.html'
    form_class = CreateConsumerForm
    success_url = reverse_lazy('list_consumers')

class DeleteConsumerView(ConsumerManagementMixin,generic.edit.DeleteView):
    model = LTIConsumer
    context_object_name = 'consumer'
    template_name = 'numbas_lti/management/confirm_delete_consumer.html'
    success_url = reverse_lazy('list_consumers')

    def form_valid(self,form):
        consumer = self.get_object()
        consumer.deleted = True
        consumer.save()

        return redirect(self.get_success_url())
