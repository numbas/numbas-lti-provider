from .mixins import MustHaveExamMixin, ResourceManagementViewMixin, MustBeInstructorMixin, request_is_instructor
from .generic import JSONView
from django import http
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect
from django.template.loader import get_template
from django_auth_lti.patch_reverse import reverse
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _, ugettext
from django.utils.text import slugify
from django.views import generic
from django.views.decorators.http import require_POST
from itertools import groupby
from numbas_lti.forms import RemarkPartScoreForm
from numbas_lti.models import Resource, AccessToken, Exam, Attempt, ScormElement, RemarkPart, AttemptLaunch
from numbas_lti.save_scorm_data import save_scorm_data
import datetime
import json
import simplejson
import string

def hierarchy_key(x):
    key = x[0]
    try:
        return int(key)
    except ValueError:
        return key

class RemarkPartsView(MustHaveExamMixin,ResourceManagementViewMixin,MustBeInstructorMixin,generic.detail.DetailView):
    model = Attempt
    template_name = 'numbas_lti/management/remark.html'
    context_object_name = 'attempt'
    management_tab = 'attempts'

    def get_resource(self):
        return self.get_object().resource

    def get_context_data(self,*args,**kwargs):
        context = super(RemarkPartsView,self).get_context_data(*args,**kwargs)

        attempt = self.get_object()
        hierarchy = attempt.part_hierarchy()
        out = []

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
                    'score': attempt.part_raw_score(path),
                    'max_score': attempt.part_max_score(path),
                    'discount': discount,
                    'remark': remark,
                    'parent_remarked': parent is not None and parent['remark'] is not None,
                    'form': RemarkPartScoreForm(instance=remark),
                    'has_gaps': has_gaps
                })

            return out

        for i,q in sorted(hierarchy.items(),key=hierarchy_key):
            qnum = int(i)+1
            out.append(row(i))

            for j,p in sorted(q.items(),key=hierarchy_key):
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

        remark,created = RemarkPart.objects.get_or_create(attempt=attempt,part=part,score=attempt.part_raw_score(part))

        template = get_template('numbas_lti/management/remark/remarked.html')
        html = template.render({
            'attempt':attempt,
            'remark':remark,
            'form':RemarkPartScoreForm(instance=remark),
            'max_score': remark.attempt.part_max_score(part),
            'path': part,
        })

        return http.JsonResponse({
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
            'score':attempt.part_raw_score(remark.part),
            'max_score':attempt.part_max_score(remark.part),
            'path':remark.part,
        })
        return http.JsonResponse({'html':html})

class RemarkPartUpdateView(MustBeInstructorMixin,generic.edit.UpdateView):
    model = RemarkPart
    form_class = RemarkPartScoreForm

    def form_valid(self,form,*args,**kwargs):
        self.object = form.save()
        return http.JsonResponse({})


class ReopenAttemptView(MustBeInstructorMixin,generic.detail.DetailView):
    model = Attempt

    def get(self, request, *args, **kwargs):
        attempt = self.get_object()
        attempt.end_time = None
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

        context['elements'] = [e.as_json() for e in self.object.scormelements.all()]
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
        context['elements'] = [e.as_json() for e in self.object.scormelements.order_by('time','counter')]
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
        raise PermissionDenied(ugettext("You can't start a new attempt at this exam."))

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

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        AttemptLaunch.objects.create(
            attempt = self.object,
            mode = self.mode,
            user = self.request.user
        )
        return response

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
            if request_is_instructor(self.request):
                mode = 'review'
            else:
                raise PermissionDenied(ugettext("You're not allowed to review this attempt."))

        context['mode'] = self.mode = mode

        user = attempt.user
        user_data = attempt.resource.user_data(user)

        scorm_cmi = attempt.scorm_cmi()

        dynamic_cmi = {
            'cmi.mode': mode,
            'cmi.entry': entry,
            'numbas.user_role': 'instructor' if request_is_instructor(self.request) else 'student',
        }
        now = datetime.datetime.now().timestamp()
        dynamic_cmi = {k: {'value':v,'time':now} for k,v in dynamic_cmi.items()}
        scorm_cmi.update(dynamic_cmi)

        context['support_name'] = getattr(settings,'SUPPORT_NAME',None)
        context['support_url'] = getattr(settings,'SUPPORT_URL',None)
        
        context['scorm_cmi'] = simplejson.encoder.JSONEncoderForHTML().encode(scorm_cmi)
        context['available_until'] = attempt.resource.available_until

        context['js_vars'] = {
            'exam_url': attempt.exam.extracted_url+'/index.html',
            'scorm_cmi': scorm_cmi,
            'attempt_pk': attempt.pk,
            'fallback_url': reverse('attempt_scorm_data_fallback', args=(attempt.pk,)),
            'show_attempts_url': reverse('show_attempts'),
            'allow_review_from': attempt.resource.allow_review_from.isoformat() if attempt.resource.allow_review_from else str(None),
            'available_until': attempt.resource.available_until.isoformat() if attempt.resource.available_until else str(None),
        }

        return context

@require_POST
def scorm_data_fallback(request,pk,*args,**kwargs):
    """ An AJAX fallback to save SCORM data, when the websocket fails """
    attempt = Attempt.objects.get(pk=pk)
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
