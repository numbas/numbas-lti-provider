from .mixins import HelpLinkMixin, ResourceManagementViewMixin, MustBeInstructorMixin, MustHaveExamMixin, INSTRUCTOR_ROLES, lti_role_or_superuser_required
from .generic import CreateFileReportView, JSONView
from numbas_lti import forms, save_scorm_data, tasks
from numbas_lti.models import \
        Resource, LTI_13_ResourceLink, AccessToken, Exam, Attempt, \
        ReportProcess, DiscountPart, EditorLink, COMPLETION_STATUSES, \
        LTIUserData, ScormElement, RemarkedScormElement, AccessChange, \
        DISCOUNT_BEHAVIOURS
from numbas_lti.util import transform_part_hierarchy
from django import http
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.core import signing
from django.db.models import Q,Count
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.template.loader import get_template
from django.template.response import TemplateResponse
from django_auth_lti.patch_reverse import reverse
from django.utils import timezone, dateparse
from django.utils.translation import gettext_lazy as _
from django.utils.text import slugify
from django.views import generic
from django_auth_lti.decorators import lti_role_required
from pathlib import Path
import csv
import datetime
import json
import itertools

class LTI_13_CreateResourceView(MustBeInstructorMixin, generic.edit.CreateView):
    model = LTI_13_ResourceLink
    management_tab = 'create_resource'
    http_methods = ['post']
    form_class = forms.LTI_13_LinkResourceForm
    template_name = 'numbas_lti/management/create_resource.html'

    def get_success_url(self):
        return self.reverse_with_lti('create_exam', args=(self.object.resource.pk,))

class CreateExamView(HelpLinkMixin, MustBeInstructorMixin, generic.edit.CreateView):
    model = Exam
    management_tab = 'create_exam'
    template_name = 'numbas_lti/management/create_exam.html'
    form_class = forms.CreateExamForm
    helplink = 'instructor/resources.html#creating-a-new-resource'

    def get_context_data(self,*args,**kwargs):
        context = super(CreateExamView,self).get_context_data(*args,**kwargs)

        context['editor_links'] = EditorLink.objects.all()
        available_exams = []
        for el in EditorLink.objects.all():
            available_exams += el.available_exams
        context['exams'] = available_exams

        return context

    def get_success_url(self):
        return self.reverse_with_lti('resource_settings', args=(self.object.resource.pk,))

class LTI_11_CreateExamView(ResourceManagementViewMixin, CreateExamView):
    def get_resource(self):
        return Resource.objects.get(pk=self.kwargs['pk'])

    def form_valid(self,form):
        resource = self.get_resource()
        exam = self.object = form.save(commit=False)
        exam.resource = resource
        exam.save()
        resource.exam = exam
        resource.save()
        return http.HttpResponseRedirect(self.get_success_url())


class ReplaceExamView(CreateExamView):
    management_tab = 'settings'
    template_name = 'numbas_lti/management/replace_exam.html'
    form_class = forms.ReplaceExamForm
    helplink = 'instructor/resources.html#replace-exam-package'

    def get_resource(self):
        return Resource.objects.get(pk=self.kwargs['pk'])

    def get_context_data(self,*args,**kwargs):
        context = super(ReplaceExamView,self).get_context_data(*args,**kwargs)

        resource = self.get_resource()
        context['resource'] = resource

        context['current_exam'] = resource.exam
        exams = []
        for exam in resource.exams.all():
            exams.append((exam,exam.attempts.count()))
        context['exams'] = exams
        context['num_attempts_other_versions'] = Attempt.objects.filter(resource=resource).exclude(exam=resource.exam).count()

        return context

    def form_valid(self,form):
        resource = self.get_resource()
        old_exam = resource.exam
        exam = self.object = form.save(commit=False)
        exam.resource = resource
        exam.save()

        if form.cleaned_data['safe_replacement']:
            resource.attempts.filter(exam=old_exam).update(exam=new_exam)

        messages.add_message(self.request,messages.INFO,_('The exam package has been updated.'))

        return http.HttpResponseRedirect(self.get_success_url())

class RestoreExamView(MustBeInstructorMixin, ResourceManagementViewMixin,generic.edit.UpdateView):
    model = Resource
    form_class = forms.RestoreExamForm

    def get_success_url(self):
        return self.reverse_with_lti('replace_exam',args=(self.get_resource().pk,))

class AttemptsUseCurrentVersionView(MustBeInstructorMixin, ResourceManagementViewMixin, generic.UpdateView):
    model = Resource
    http_method_names = ['post']

    def post(self, request, *args, **kwargs):
        resource = self.get_resource()
        with transaction.atomic():
            for a in Attempt.objects.filter(resource=resource).exclude(exam=resource.exam):
                a.exam = resource.exam
                a.save()
        messages.add_message(self.request,messages.INFO,_('All attempts now use the active version of this resource\'s exam.'))
        return redirect(self.reverse_with_lti('replace_exam',args=(resource.pk,)))

class DashboardView(HelpLinkMixin, MustHaveExamMixin,ResourceManagementViewMixin,MustBeInstructorMixin,generic.detail.DetailView):
    model = Resource
    template_name = 'numbas_lti/management/dashboard.html'
    management_tab = 'dashboard'
    helplink = 'instructor/resources.html#dashboard'

    def get_exam_info(self):
        content = self.get_object().exam.source()
        if content is None:
            return
        nav = content.get('navigation',{})
        timing = content.get('timing',{})
        feedback = content.get('feedback',{})

        showResultsPage =nav.get('showresultspage')
        duration = content.get('duration')
        percentPass = content.get('percentPass')
        info = {
            'hasPercentPass': percentPass and percentPass != '0',
            'percentPass':  percentPass,
            'hasTimeLimit': duration and duration != '0',
            'duration':  int(duration)/60 if duration else None,
            'allowPrinting':  content.get('allowPrinting'),

            'allowRegen':  nav.get('allowregen'),
            'allowReverse':  nav.get('reverse'),
            'allowBrowse':  nav.get('browse'),
            'allowSteps':  nav.get('allowsteps'),

            'completionShowResultsPage': showResultsPage == 'oncompletion',
            'reviewShowResultsPage': showResultsPage == 'oncompletion' or showResultsPage == 'review',

            'leaveUnattempted': nav.get('onleave',{}).get('action') != 'preventifunattempted',
            
            'navigateMode':  nav.get('navigatemode'),
            'startPassword':  nav.get('startpassword'),

            'allowPause':  timing.get('allowPause'),

            'showActualMark':  feedback.get('showactualmark'),
            'showTotalMark':  feedback.get('showTotalMark'),
            'showAnswerState':  feedback.get('showanswerstate'),
            'allowRevealAnswer':  feedback.get('allowrevealanswer'),
            'reviewShowScore':  feedback.get('reviewshowscore'),
            'reviewShowFeedback':  feedback.get('reviewshowfeedback'),
            'reviewShowAdvice':  feedback.get('reviewshowadvice'),
            'reviewShowExpectedAnswer': feedback.get('reviewshowexpectedanswer'),
        }
        return info

    def get_context_data(self,*args,**kwargs):
        context = super(DashboardView,self).get_context_data(*args,**kwargs)

        resource = self.get_object()

        context['exam_info'] = self.get_exam_info()

        context['instructors'] = User.objects.filter(lti_data__in=LTIUserData.objects.filter(resource=resource,is_instructor=True)).distinct()

        context['num_unbroken_attempts'] = resource.attempts.exclude(broken=True).count()

        context['students'] = User.objects.filter(attempts__resource=resource).exclude(attempts__deleted=True).distinct()
        last_report_process = resource.report_processes.first()
        if last_report_process and last_report_process.dismissed and last_report_process.status == 'reporting':
            context['dismissed_report_process'] = last_report_process
        if last_report_process and (not last_report_process.dismissed):
            context['last_report_process'] = last_report_process

        return context

class StudentProgressView(HelpLinkMixin,MustHaveExamMixin,ResourceManagementViewMixin,MustBeInstructorMixin,generic.detail.DetailView):
    model = Resource
    template_name = 'numbas_lti/management/student_progress.html'
    management_tab = 'dashboard'
    helplink = 'instructor/resources.html#student-progress'

    def get_context_data(self,*args,**kwargs):
        context = super().get_context_data(*args,**kwargs)

        resource = self.get_object()

        context['unlimited_attempts'] = resource.max_attempts == 0

        students = resource.students().all()

        def summarise_extra_student(student):
            return {
                'last_name': student['family_name'],
                'first_name': student['given_name'],
                'full_name': student['name'],
                'reported_score': 0,
                'score': 0,
                'lti_data': None,
                'attempts': 0,
                'access_tokens': 0,
            }

        def summarise_student(student):
            attempt = resource.grade_user(student)
            score = attempt.scaled_score if attempt else 0
            lti_data = student.lti_data.filter(resource=resource).last()

            if is_lti_13:
                subs = student.lti_13_aliases.all().values_list('sub', flat=True)
                grades = [g for g in ags_grades if g['userId'] in subs]
                grade = grades[0] if grades else None
                reported_score = (grade['resultScore'] / grade['resultMaximum']) if grade else None
                score_not_reported = reported_score != score
            else:
                reported_score = lti_data.last_reported_score

            return {
                'last_name': student.last_name,
                'first_name': student.first_name,
                'full_name': student.get_full_name(),
                'reported_score': reported_score,
                'score': score,
                'lti_data': lti_data,
                'attempts': Attempt.objects.filter(user=student,resource=resource).exclude(broken=True).count(),
                'access_tokens': AccessToken.objects.filter(user=student,resource=resource).count(),
            }

        message_launch = self.get_message_launch()
        if message_launch:
            ags = self.get_message_launch().get_ags()
            lineitem = resource.get_lti_13_lineitem(ags)
            ags_grades = context['grades'] = ags.get_grades(lineitem)
            is_lti_13 = context['is_lti_13'] = True
            nrps_members = [m for m in self.get_nrps_members() if m['student']]
            got_ids = [s for student in students for s in student.lti_13_aliases.all().values_list('sub', flat=True)]
            extra_students = [summarise_extra_student(m) for m in nrps_members if m['user_id'] not in got_ids]
        else:
            is_lti_13 = context['is_lti_13'] = False
            extra_students = []

        summaries = [summarise_student(student) for student in students] + extra_students

        context['student_summary'] = sorted(summaries, key=lambda x: (x['last_name'], x['first_name']))


        return context


class DiscountPartsView(HelpLinkMixin,MustHaveExamMixin,ResourceManagementViewMixin,MustBeInstructorMixin,generic.detail.DetailView):
    model = Resource
    template_name = 'numbas_lti/management/discount.html'
    context_object_name = 'resource'
    management_tab = 'dashboard'
    helplink = 'instructor/resources.html#discount-question-parts'

    def get_parts(self):
        resource = self.get_object()

        def row(q,p,g,qnum,path,pletter,**kwargs):
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

        parts = transform_part_hierarchy(resource.part_hierarchy(),row)

        return parts


    def get_context_data(self,*args,**kwargs):
        context = super(DiscountPartsView,self).get_context_data(*args,**kwargs)

        context['discount_behaviours'] = DISCOUNT_BEHAVIOURS
        context['parts'] = self.get_parts()

        return context

    def post(self, request, *args, **kwargs):
        resource = self.get_object()
        parts = self.get_parts()

        for part in parts:
            if part['p'] is None:
                continue
            behaviour = request.POST.get('discount-'+part['path'])
            if behaviour:
                discount, created = DiscountPart.objects.get_or_create(resource=resource,part=part['path'])
                discount.behaviour = behaviour
                discount.save()
            else:
                DiscountPart.objects.filter(resource=resource,part=part['path']).delete()

        tasks.resource_update_score_info(resource)

        messages.add_message(request,messages.SUCCESS,_('Part discounts have been saved. It might take a while for individual attempts\' scores to be updated.'))

        return self.get(request,*args,**kwargs)

class ResourceSettingsView(HelpLinkMixin,MustHaveExamMixin,ResourceManagementViewMixin,MustBeInstructorMixin,generic.edit.UpdateView):
    model = Resource
    form_class = forms.ResourceSettingsForm
    template_name = 'numbas_lti/management/resource_settings.html'
    context_object_name = 'resource'
    management_tab = 'settings'
    helplink = 'instructor/resources.html#settings'

    def get_success_url(self):
        return self.reverse_with_lti('resource_dashboard',args=(self.get_object().pk,))

class CreateResourceFileReportView(MustBeInstructorMixin,CreateFileReportView,generic.detail.DetailView):
    model = Resource

    def get_resource(self):
        return self.object

    def get_success_url(self):
        return self.reverse_with_lti('resource_dashboard',args=(self.object.pk,))

class FileReportsListView(HelpLinkMixin,MustBeInstructorMixin,ResourceManagementViewMixin,generic.detail.DetailView):
    template_name = 'numbas_lti/management/resource_reports.html'
    model = Resource
    context_object_name = 'resource'
    management_tab = 'reports'
    helplink = 'instructor/resources.html#reports'

class ScoresCSV(CreateResourceFileReportView):
    report_task = tasks.resource_scores_csv_report

    def get_name(self):
        return 'Scores CSV'

    def get_filename(self):
        return _("{slug}-scores.csv").format(slug=self.object.slug)

class JSONDumpView(CreateResourceFileReportView):
    report_task = tasks.resource_json_dump_report

    def get_name(self):
        return 'JSON dump'

    def get_task_kwargs(self):
        return {'full': 'full' in self.request.POST}

    def get_filename(self):
        resource = self.object
        return _("{slug}-attempts_data.json").format(slug=resource.slug)

class AttemptsCSV(CreateResourceFileReportView):
    report_task = tasks.resource_attempts_csv_report

    def get_name(self):
        return 'Attempts CSV'

    def get_filename(self):
        return _("{slug}-attempts.csv").format(slug=self.object.slug)

class ReportAllScoresView(MustHaveExamMixin,MustBeInstructorMixin,ResourceManagementViewMixin,generic.detail.DetailView):
    model = Resource
    management_tab = 'dashboard'
    template_name = 'numbas_lti/management/report_all_scores.html'
    context_object_name = 'resource'

    def get(self,*args,**kwargs):
        resource = self.get_object()
        resource.task_report_scores()
        return super(ReportAllScoresView,self).get(*args,**kwargs)

@lti_role_or_superuser_required(INSTRUCTOR_ROLES)
def grant_access_token(request,resource_id,user_id):
    resource = Resource.objects.get(pk=resource_id)
    user = User.objects.get(id=user_id)
    AccessToken.objects.create(user=user,resource=resource)

    return redirect(self.reverse_with_lti('resource_dashboard',args=(resource.pk,)))

@lti_role_or_superuser_required(INSTRUCTOR_ROLES)
def remove_access_token(request,resource_id,user_id):
    resource = Resource.objects.get(pk=resource_id)
    user = User.objects.get(id=user_id)
    AccessToken.objects.filter(user=user,resource=resource).first().delete()

    return redirect(self.reverse_with_lti('resource_dashboard',args=(resource.pk,)))

class DismissReportProcessView(MustBeInstructorMixin,generic.detail.DetailView):
    model = ReportProcess

    def render_to_response(self,context):
        process = self.get_object()
        process.dismissed = True
        process.save()
        return redirect(self.reverse_with_lti('resource_dashboard',args=(process.resource.pk,)))

class RunExamView(MustHaveExamMixin,MustBeInstructorMixin,ResourceManagementViewMixin,generic.detail.DetailView):
    """
        Run an exam without saving any attempt data
    """
    management_tab = 'test_run'
    model = Exam
    template_name = 'numbas_lti/management/run_exam.html'
    context_object_name = 'exam'

    def get_resource(self):
        exam = self.get_object()
        if exam.resource:
            return exam.resource
        else:
            return Resource.objects.filter(exam=exam).first()

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

class AllAttemptsView(HelpLinkMixin,MustHaveExamMixin,ResourceManagementViewMixin,MustBeInstructorMixin,generic.ListView):
    model = Attempt
    template_name = 'numbas_lti/management/attempts.html'
    management_tab = 'attempts'
    paginate_by = 20
    context_object_name = 'attempts'
    helplink = 'instructor/resources.html#attempts'

    def get_queryset(self, *args, **kwargs):
        self.query = ''
        resource = self.get_resource()
        attempts = resource.attempts.all()
        if self.request.GET.get('userid'):
            try:
                user = User.objects.get(pk=int(self.request.GET['userid']))
                self.query = user.get_full_name()
                attempts = attempts.filter(user=user)
            except (ValueError, User.DoesNotExist):
                pass
        elif 'query' in self.request.GET:
            query = self.query = self.request.GET.get('query')
            for word in query.split():
                attempts = attempts.filter(Q(user__first_name__icontains=word) | Q(user__last_name__icontains=word))
        return attempts

    def get_resource(self):
        return Resource.objects.get(pk=self.kwargs.get('pk'))

    def get_context_data(self, *args, **kwargs):
        context = super(AllAttemptsView,self).get_context_data(*args,**kwargs)
        resource = self.get_resource()
        context['resource'] = resource
        context['query'] = self.query

        return context

class StatsView(HelpLinkMixin,MustHaveExamMixin,ResourceManagementViewMixin,MustBeInstructorMixin,generic.DetailView):
    model = Resource
    template_name = 'numbas_lti/management/resource_stats.html'
    management_tab = 'stats'
    helplink = 'instructor/resources.html#statistics'

    def get_context_data(self, *args, **kwargs):
        context = super(StatsView,self).get_context_data(*args, **kwargs)

        resource = self.object

        completion_counts = resource.attempts.values('completion_status').order_by('completion_status').annotate(number=Count('completion_status'))
        completion_dict = {x['completion_status']: x['number'] for x in completion_counts}
        context['completion_counts'] = [
            (label, value, completion_dict.get(value,0)) for value,label in COMPLETION_STATUSES
        ]

        context['data'] = resource.live_stats_data()

        return context

class RemarkView(HelpLinkMixin,MustHaveExamMixin,ResourceManagementViewMixin,MustBeInstructorMixin,generic.DetailView):
    model = Resource
    template_name = 'numbas_lti/management/resource_remark.html'
    management_tab = 'remark'
    helplink = 'instructor/resources.html#remark'

    def get(self, request, *args, **kwargs):
        resource = self.object = self.get_object()
        if not resource.exam.supports_feature('run_headless'):
            return TemplateResponse(
                request=self.request,
                template=['numbas_lti/management/resource_remark_not_supported.html'],
                context=super().get_context_data(object=self.object),
                using=self.template_engine
            )
        return super().get(request, *args, **kwargs)

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args,**kwargs)

        resource = self.object
        attempts = resource.unbroken_attempts()

        context['attempts'] = [
            {
                'pk': a.pk,
                'completion_status': a.completion_status,
                'start_time': a.start_time,
                'user': { 
                    'full_name': a.user.get_full_name(),
                    'identifier': a.user_data().identifier(),
                },
            }
            for a in attempts
        ]

        context['parameters'] = {
            'save_url': self.reverse_with_lti('resource_remark_save_data',args=(resource.pk,)),
        }

        source_path = Path(resource.exam.extracted_path) / 'source.exam'
        if source_path.exists():
            with open(str(source_path)) as f:
                text = f.read()
                i = text.find('\n')
                data = json.loads(text[i+1:])
                context['exam_source'] = data

        return context

class RemarkGetAttemptDataView(MustHaveExamMixin,ResourceManagementViewMixin,MustBeInstructorMixin,generic.DetailView):
    """ 
        Get the SCORM CMI for the given attempts 
    """
    model = Resource

    def get(self,request,*args,**kwargs):
        pks = request.GET.get('attempt_pks','')
        if pks:
            pks = [int(x) for x in pks.split(',')]
        else:
            pks = []
        attempts = self.resource.attempts.filter(pk__in=pks)

        cmis = []
        for a in attempts:
            cmi = a.scorm_cmi(include_remarked_elements=False)

            dynamic_cmi = {
                'cmi.mode': 'normal',
                'cmi.entry': 'resume',
                'cmi.completion_status': 'incomplete',
                'numbas.user_role': 'student',
            }
            etime = datetime.datetime.now().timestamp()
            dynamic_cmi = {k: {'value':v,'time':etime} for k,v in dynamic_cmi.items()}
            cmi.update(dynamic_cmi)
            cmis.append({
                'pk': a.pk, 
                'raw_score': a.raw_score,
                'max_score': a.max_score,
                'cmi': cmi
                })

        return JsonResponse({'cmis': cmis})

class RemarkSaveChangedDataView(MustHaveExamMixin, ResourceManagementViewMixin, MustBeInstructorMixin, generic.UpdateView):
    """
        Save changed SCORM elements after remarking
    """
    model = Resource

    def post(self, request, *args, **kwargs):
        saved = []
        try:
            data = json.loads(request.body.decode())
            now = timezone.make_aware(datetime.datetime.now())
            with transaction.atomic():
                for ad in data['attempts']:
                    try:
                        attempt = Attempt.objects.get(pk=ad['pk'])
                    except Attempt.DoesNotExist:
                        continue

                    new_elements = []
                    for k,v in ad['changed_keys'].items():
                        e = ScormElement.objects.create(attempt=attempt, key=k, value=v, time=now, counter=0)
                        new_elements.append(e)
                        RemarkedScormElement.objects.create(element=e,user=request.user)

                    save_scorm_data.update_question_score_info(attempt, new_elements)
                    saved.append(ad['pk'])
            response = {'success': True, 'saved': saved}
            if len(saved)<len(data['attempts']):
                response['success'] = False
                response['message'] = _("There was an error while saving some data.")
            return JsonResponse(response, status=200 if response['success'] else 500)
        except Exception as err:
            return JsonResponse({'success': False, 'message': str(err), 'saved': saved},status=500)

class RemarkIframeView(MustHaveExamMixin,ResourceManagementViewMixin,MustBeInstructorMixin,generic.DetailView):
    model = Resource
    template_name = 'numbas_lti/management/resource_remark_iframe.html'
    management_tab = 'remark'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args,**kwargs)
        resource = self.object
        context['exam_data'] = {
            'extracted_url': resource.exam.extracted_url,
        }
        context['scripts_url'] = resource.exam.extracted_url +'/scripts.js'
        return context

class ValidateReceiptView(HelpLinkMixin,ResourceManagementViewMixin,MustBeInstructorMixin,generic.detail.SingleObjectMixin,generic.FormView):
    model = Resource
    form_class = forms.ValidateReceiptForm
    template_name = 'numbas_lti/management/validate_receipt.html'
    management_tab = 'dashboard'
    helplink = 'instructor/resources.html#validate-a-receipt-code'
    
    def dispatch(self,request,*args,**kwargs):
        self.object = self.get_object()
        return super().dispatch(request,*args,**kwargs)

    def get(self,request,*args,**kwargs):
        return super().get(request,*args,**kwargs)

    def form_valid(self, form):
        code = form.cleaned_data['code']
        salt = self.object.receipt_salt()
        context = self.get_context_data()
        context['form'] = form
        context['submitted'] = True
        try:
            summary = signing.loads(code,salt=salt)
            for k in ('receipt_time','start_time','end_time'):
                if k in summary and summary[k] is not None:
                    summary[k] = dateparse.parse_datetime(summary[k])
            context['summary'] = summary
            attempt = Attempt.objects.get(pk=summary['pk'],resource=self.object)
            context['attempt'] = attempt
            context['valid'] = True
            return self.render_to_response(context)
        except signing.BadSignature:
            context['invalid'] = True
            pass
        except Attempt.DoesNotExist:
            context['no_attempt'] = True

        return self.render_to_response(context)

class AccessChangesView(HelpLinkMixin,ResourceManagementViewMixin, MustBeInstructorMixin, generic.ListView):
    model = AccessChange
    template_name = 'numbas_lti/management/access_change/list.html'
    management_tab = 'access-changes'
    resource_pk_url_kwarg = 'resource_id'
    helplink = 'instructor/resources.html#access-changes'
    
class AccessChangeEditView(HelpLinkMixin, ResourceManagementViewMixin, MustBeInstructorMixin):
    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)

        context['nrps_members'] = self.get_nrps_members()

        return context

class CreateAccessChangeView(AccessChangeEditView, generic.CreateView):
    model = AccessChange
    form_class = forms.AccessChangeForm
    template_name = 'numbas_lti/management/access_change/edit.html'
    management_tab = 'access-changes'
    resource_pk_url_kwarg = 'resource_id'
    helplink = 'instructor/resources.html#access-changes'

    extra_context = {
        'create': True,
    }

    def get_initial(self):
        initial = super().get_initial()
        initial['resource'] = self.get_resource()

        return initial

    def get_success_url(self):
        return self.reverse_with_lti('resource_access_changes',args=(self.get_resource().pk,))

class UpdateAccessChangeView(AccessChangeEditView, generic.UpdateView):
    model = AccessChange
    form_class = forms.AccessChangeForm
    management_tab = 'access-changes'
    template_name = 'numbas_lti/management/access_change/edit.html'
    helplink = 'instructor/resources.html#access-changes'

    def get_resource(self):
        return self.get_object().resource

    def get_success_url(self):
        return self.reverse_with_lti('resource_access_changes',args=(self.get_resource().pk,))

    def get_initial(self):
        initial = super().get_initial()
        ac = self.get_object()
        initial['resource'] = ac.resource
        usernames = [u.username for u in ac.usernames.all()]
        initial['nrps_applies_to'] = usernames
        initial['usernames'] = '\n'.join(usernames)
        initial['emails'] = '\n'.join(e.email for e in ac.emails.all())
        if ac.extend_deadline is not None:
            initial['extend_deadline_days'] = ac.extend_deadline.days
            initial['extend_deadline_minutes'] = ac.extend_deadline.seconds // 60
        return initial

class DeleteAccessChangeView(HelpLinkMixin,ResourceManagementViewMixin, MustBeInstructorMixin, generic.DeleteView):
    model = AccessChange
    management_tab = 'settings'
    template_name = 'numbas_lti/management/access_change/delete.html'
    helplink = 'instructor/resources.html#access-changes'

    def get_resource(self):
        return self.get_object().resource

    def get_success_url(self):
        return self.reverse_with_lti('resource_access_changes',args=(self.get_resource().pk,))
