from .mixins import ResourceManagementViewMixin, MustBeInstructorMixin, MustHaveExamMixin, INSTRUCTOR_ROLES
from .generic import CSVView
from numbas_lti import forms
from numbas_lti.models import Resource, AccessToken, Exam, Attempt, ReportProcess, DiscountPart, EditorLink, COMPLETION_STATUSES
from channels import Channel
from django import http
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Q,Count
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.template.loader import get_template
from django_auth_lti.patch_reverse import reverse
from django.utils.translation import ugettext_lazy as _
from django.views import generic
from django_auth_lti.decorators import lti_role_required
import csv
import json
import string

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

        context['unlimited_attempts'] = resource.max_attempts == 0

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

def hierarchy_key(x):
    key = x[0]
    try:
        return int(key)
    except ValueError:
        return key

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

        for i,q in sorted(hierarchy.items(),key=hierarchy_key):
            qnum = int(i)+1
            out.append(row(i))

            for j,p in sorted(q.items(),key=hierarchy_key):
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

class ResourceSettingsView(MustHaveExamMixin,ResourceManagementViewMixin,MustBeInstructorMixin,generic.edit.UpdateView):
    model = Resource
    form_class = forms.ResourceSettingsForm
    template_name = 'numbas_lti/management/resource_settings.html'
    context_object_name = 'resource'
    management_tab = 'settings'

    def get_success_url(self):
        return reverse('dashboard',args=(self.get_object().pk,))

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
                student.username,
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
                attempt.user.username,
                attempt.start_time,
                attempt.completion_status,
                attempt.raw_score,
                attempt.scaled_score*100,
            ]+[attempt.question_raw_score(n) for n in range(num_questions)]
            yield row

    def get_filename(self):
        return _("{slug}-attempts.csv").format(slug=self.object.slug)

class ReportAllScoresView(MustHaveExamMixin,MustBeInstructorMixin,ResourceManagementViewMixin,generic.detail.DetailView):
    model = Resource
    management_tab = 'dashboard'
    template_name = 'numbas_lti/management/report_all_scores.html'
    context_object_name = 'resource'

    def get(self,*args,**kwargs):
        Channel("report.all_scores").send({'pk':self.get_object().pk})
        return super(ReportAllScoresView,self).get(*args,**kwargs)

@lti_role_required(INSTRUCTOR_ROLES)
def grant_access_token(request,user_id):
    user = User.objects.get(id=user_id)
    AccessToken.objects.create(user=user,resource=request.resource)

    return redirect(reverse('dashboard',args=(request.resource.pk,)))

@lti_role_required(INSTRUCTOR_ROLES)
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
                attempts = attempts.filter(Q(user__first_name__icontains=word) | Q(user__last_name__icontains=word))
        return attempts

    def get_resource(self):
        return Resource.objects.get(pk=self.kwargs.get('pk'))

    def get_context_data(self, *args, **kwargs):
        context = super(AllAttemptsView,self).get_context_data(*args,**kwargs)
        resource = self.get_resource()
        context['resource'] = resource

        return context

class StatsView(MustHaveExamMixin,ResourceManagementViewMixin,MustBeInstructorMixin,generic.DetailView):
    model = Resource
    template_name = 'numbas_lti/management/resource_stats.html'
    management_tab = 'stats'

    def get_context_data(self, *args, **kwargs):
        context = super(StatsView,self).get_context_data(*args, **kwargs)

        resource = self.object
        completion_counts = resource.attempts.values('completion_status').order_by('completion_status').annotate(number=Count('completion_status'))
        completion_dict = {x['completion_status']: x['number'] for x in completion_counts}
        context['completion_counts'] = [
            (label, completion_dict.get(value,0)) for value,label in COMPLETION_STATUSES
        ]

        attempt_scores = resource.attempts.values('scaled_score').order_by('scaled_score').annotate(number=Count('scaled_score'))
        cumulative_scores = []
        t = 0
        for item in reversed(attempt_scores):
            cumulative_scores.insert(0,{'score': item['scaled_score'],'n': t})
            t += item['number']
        cumulative_scores.append({'score': 1.0,'n':0})
        context['cumulative_scores'] = json.dumps(cumulative_scores)

        return context
