from .mixins import MustHaveExamMixin, ResourceManagementViewMixin, MustBeInstructorMixin, request_is_instructor
from .generic import JSONView
import datetime
from django import http
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect
from django.template.loader import get_template
from django_auth_lti.patch_reverse import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _, gettext
from django.utils.text import slugify
from django.views import generic
from django.views.decorators.http import require_POST
from itertools import groupby
import json
from numbas_lti import tasks
from numbas_lti.forms import RemarkPartScoreForm
from numbas_lti.models import Resource, AccessToken, Exam, Attempt, ScormElement, RemarkPart, AttemptLaunch, resolve_diffed_scormelements, RemarkedScormElement
from numbas_lti.save_scorm_data import save_scorm_data
from numbas_lti.util import transform_part_hierarchy
import re
import simplejson

class RemarkPartsView(MustHaveExamMixin,ResourceManagementViewMixin,MustBeInstructorMixin,generic.detail.DetailView):
    model = Attempt
    template_name = 'numbas_lti/management/attempt_remark.html'
    context_object_name = 'attempt'
    management_tab = 'attempts'

    def get_resource(self):
        return self.get_object().resource

    def get_parts(self):
        attempt = self.get_object()

        def row(qnum,q,p,g,parent,has_gaps,path,pletter,**kwargs):

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
                    'score': attempt.part_raw_score(path),
                    'original_score': attempt.part_raw_score(path,include_remark=False),
                    'max_score': attempt.part_max_score(path),
                    'discount': discount,
                    'remark': remark,
                    'parent_remarked': parent is not None and parent['remark'] is not None,
                    'form': RemarkPartScoreForm(instance=remark),
                    'has_gaps': has_gaps
                })

            return out

        parts = transform_part_hierarchy(attempt.part_hierarchy(), row)

        return parts

    def get_context_data(self,*args,**kwargs):
        context = super().get_context_data(*args,**kwargs)

        context['parts'] = self.get_parts()

        return context

    def post(self, request, *args, **kwargs):
        attempt = self.get_object()
        parts = self.get_parts()
        for part in parts:
            if part['p'] is None:
                continue
            remark = request.POST.get('remark-'+part['path'])
            score = request.POST.get('score-'+part['path'])
            if remark:
                remark, created = RemarkPart.objects.get_or_create(attempt=attempt, part=part['path'])
                remark.score = score
                remark.save()
            else:
                RemarkPart.objects.filter(attempt=attempt,part=part['path']).delete()

        changed_questions = set(int(re.match(r'^q(\d+)',v).group(1)) for v in attempt.remarked_parts.values_list('part',flat=True))
        tasks.attempt_update_score_info(attempt, changed_questions)

        return self.get(request,*args,**kwargs)

class ReopenAttemptView(MustBeInstructorMixin,generic.detail.DetailView):
    model = Attempt

    def get(self, request, *args, **kwargs):
        attempt = self.get_object()
        e = ScormElement.objects.create(
                attempt=attempt,
                key='cmi.completion_status',
                value='incomplete',
                time=timezone.now(),
                counter=1
            )
        messages.add_message(self.request,messages.SUCCESS,_('{}\'s attempt has been reopened.'.format(attempt.user.get_full_name())))
        return redirect(reverse('manage_attempts',args=(attempt.resource.pk,)))

class AttemptSCORMListing(MustHaveExamMixin,MustBeInstructorMixin,ResourceManagementViewMixin,generic.detail.DetailView):
    model = Attempt
    management_tab = 'attempts'
    template_name = 'numbas_lti/management/attempt_scorm_listing.html'
    context_object_name = 'attempt'

    def get_resource(self):
        return self.get_object().resource

    def get_context_data(self,*args,**kwargs):
        context = super(AttemptSCORMListing,self).get_context_data(*args,**kwargs)

        context['elements'] = [e.as_json() for e in resolve_diffed_scormelements(self.object.scormelements.all())]
        context['show_stale_elements'] = True
        context['resource'] = self.object.resource

        return context

class AttemptTimelineView(MustHaveExamMixin,MustBeInstructorMixin,ResourceManagementViewMixin,generic.detail.DetailView):
    model = Attempt
    management_tab = 'attempts'
    template_name = 'numbas_lti/management/attempt_timeline.html'
    context_object_name = 'attempt'

    def get_resource(self):
        return self.get_object().resource

    def get_context_data(self,*args,**kwargs):
        context = super().get_context_data(*args,**kwargs)

        context['resource'] = self.object.resource
        context['elements'] = [e.as_json() for e in resolve_diffed_scormelements(self.object.scormelements.reverse())]
        context['remarked_elements'] = [r.as_json() for r in RemarkedScormElement.objects.filter(element__attempt=self.object)]
        context['launches'] = [l.as_json() for l in self.object.launches.all()]

        return context

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


class ShowAttemptsView(generic.list.ListView):
    model = Attempt
    template_name = 'numbas_lti/show_attempts.html'

    ordering = ['start_time']

    def get_queryset(self):
        return Attempt.objects.filter(resource=self.request.resource,user=self.request.user).exclude(broken=True)

    def dispatch(self,request,*args,**kwargs):
        if request.GET.get('back_from_unsaved_complete_attempt'):
            messages.add_message(self.request,messages.INFO,_('The attempt was completed, but not all data had been saved. All data has now been saved, and review is not available yet.'))

        if not hasattr(request,'resource'):
            raise http.Http404("There's no resource attached to this request.")

        if not self.get_queryset().exists():
            resource = request.resource
            if not resource.is_available(request.user):
                now = timezone.now()
                available_from, available_until = resource.available_for_user(request.user)
                if available_from is not None and now < available_from:
                    template = get_template('numbas_lti/not_available_yet.html')
                    raise PermissionDenied(template.render({'available_from': available_from}))

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
        raise PermissionDenied(gettext("You can't start a new attempt at this exam."))

    resource = request.resource
    user = request.user

    max_attempts = resource.max_attempts_for_user(user)

    num_attempts = Attempt.objects.filter(resource=request.resource,user=request.user).count()

    if num_attempts >= max_attempts:
        tokens = AccessToken.objects.filter(resource=request.resource,user=request.user)
        if tokens.exists():
            tokens.first().delete()
        else:
            if not request.resource.can_start_new_attempt(request.user):
                raise PermissionDenied(gettext("You can't start a new attempt at this exam."))

    attempt = Attempt.objects.create(
        resource = request.resource,
        exam = request.resource.exam,
        user = request.user
    )
    return redirect(reverse('run_attempt',args=(attempt.pk,)))

class BrokenAttemptException(Exception):
    def __init__(self,attempt):
        self.attempt = attempt

class RunAttemptView(generic.detail.DetailView):
    model = Attempt
    context_object_name = 'attempt'

    template_name = 'numbas_lti/run_attempt.html'

    def get(self, request, *args, **kwargs):
        try:
            response = super().get(request, *args, **kwargs)
        except BrokenAttemptException as e:
            response = http.HttpResponseServerError(_("This attempt is broken - there isn't enough saved SCORM data to resume it."))
            self.mode = 'broken'
        AttemptLaunch.objects.create(
            attempt = self.object,
            mode = self.mode,
            user = self.request.user
        )
        return response

    def get_context_data(self,*args,**kwargs):
        context = super(RunAttemptView,self).get_context_data(*args,**kwargs)

        attempt = self.get_object()

        try:
            completion_status = attempt.scormelements.current('cmi.completion_status')
        except ScormElement.DoesNotExist:
            completion_status = 'not attempted'

        if completion_status=='not attempted':
            entry = 'ab-initio'
        elif attempt.scormelements.filter(key='cmi.suspend_data').exists():
            entry = 'resume'
        else:
            # Not enough data was saved last time. Mark this attempt as broken, and create a new one.
            # This isn't ideal, because what's happening isn't made clear to the student, but this should only occur when the student didn't really start the attempt they're resuming
            broken_attempt = attempt
            broken_attempt.broken = True
            broken_attempt.save()

            if attempt.user != self.request.user:
                raise BrokenAttemptException(attempt)

            attempt = Attempt.objects.create(
                resource = broken_attempt.resource,
                exam = broken_attempt.exam,
                user = broken_attempt.user
            )
            entry = 'ab-initio'
            context['attempt'] = attempt


        if attempt.completed():
            mode = 'review'
        else:
            mode = 'normal'

        if attempt.user != self.request.user:
            user_data = attempt.resource.user_data(self.request.user)
            if (user_data is not None and user_data.is_instructor) or request_is_instructor(self.request):
                mode = 'review'
            else:
                raise PermissionDenied(gettext("You're not allowed to review this attempt."))

        context['mode'] = self.mode = mode

        user = attempt.user
        available_from, available_until = attempt.resource.available_for_user(user)

        scorm_cmi = attempt.scorm_cmi()


        duration_extension_amount, duration_extension_units = attempt.resource.duration_extension_for_user(user)
        dynamic_cmi = {
            'cmi.mode': mode,
            'cmi.entry': entry,
            'numbas.user_role': 'instructor' if request_is_instructor(self.request) else 'student',
            'numbas.duration_extension.amount': duration_extension_amount,
            'numbas.duration_extension.units': duration_extension_units,
        }

        now = datetime.datetime.now().timestamp()
        dynamic_cmi = {k: {'value':v,'time':now} for k,v in dynamic_cmi.items()}
        scorm_cmi.update(dynamic_cmi)

        context['support_name'] = getattr(settings,'SUPPORT_NAME',None)
        context['support_url'] = getattr(settings,'SUPPORT_URL',None)
        
        context['scorm_cmi'] = simplejson.encoder.JSONEncoderForHTML().encode(scorm_cmi)
        context['available_until'] = available_until

        context['js_vars'] = {
            'exam_url': attempt.exam.extracted_url+'/index.html',
            'scorm_cmi': scorm_cmi,
            'attempt_pk': attempt.pk,
            'fallback_url': reverse('attempt_scorm_data_fallback', args=(attempt.pk,)),
            'show_attempts_url': reverse('show_attempts'),
            'allow_review_from': attempt.resource.allow_review_from.isoformat() if attempt.resource.allow_review_from else None,
            'available_from': available_from.isoformat() if available_from else None,
            'available_until': available_until.isoformat() if available_until else None,
        }

        return context

@require_POST
def scorm_data_fallback(request,pk,*args,**kwargs):
    """ An AJAX fallback to save SCORM data, when the websocket fails """
    try:
        attempt = Attempt.objects.get(pk=pk)
    except Attempt.DoesNotExist:
        raise http.Http404(_("There is no attempt with the ID {}.").format(pk))
    data = json.loads(request.body.decode())
    batches = data.get('batches',[])
    done, unsaved_elements = save_scorm_data(attempt,batches)
    complete = data.get('complete',False)
    response = {
        'received_batches':done,
        'unsaved_elements':unsaved_elements, 
    }
    if complete:
        attempt.finalise()
        attempt.all_data_received = True
        attempt.save(update_fields=['all_data_received'])
        receipt_context = attempt.completion_receipt_context()
        response['signed_receipt'] = receipt_context['signed_summary']

    return http.JsonResponse(response)


class JSONDumpView(MustBeInstructorMixin,JSONView,generic.detail.DetailView):
    model = Attempt

    def get_resource(self):
        return self.get_object().resource

    def get_data(self):
       attempt = self.get_object()
       return attempt.data_dump(include_all_scorm=True)

    def get_filename(self):
        attempt = self.get_object()
        return '{context}--{resource}--attempt-{attempt}.json'.format(
            context=slugify(attempt.resource.context.name),
            resource=attempt.resource.slug,
            attempt=attempt.pk
        )
