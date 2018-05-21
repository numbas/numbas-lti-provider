from .mixins import MustHaveExamMixin, ResourceManagementViewMixin, MustBeInstructorMixin, request_is_instructor
from django import http
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.template.loader import get_template
from django_auth_lti.patch_reverse import reverse
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _, ugettext
from django.views import generic
from django.views.decorators.http import require_POST
from itertools import groupby
from numbas_lti.forms import RemarkPartScoreForm
from numbas_lti.models import Resource, AccessToken, Exam, Attempt, ScormElement, RemarkPart
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

        context['keys'] = [(x,list(y)) for x,y in groupby(self.object.scormelements.order_by('key','-time','-counter'),key=lambda x:x.key)]
        context['show_stale_elements'] = True

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
            'numbas.user_role': 'instructor' if request_is_instructor(self.request) else 'student',
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

        context['support_name'] = getattr(settings,'SUPPORT_NAME',None)
        context['support_url'] = getattr(settings,'SUPPORT_URL',None)
        
        context['scorm_cmi'] = simplejson.encoder.JSONEncoderForHTML().encode(scorm_cmi)

        return context

@require_POST
def scorm_data_fallback(request,pk,*args,**kwargs):
    """ An AJAX fallback to save SCORM data, when the websocket fails """
    attempt = Attempt.objects.get(pk=pk)
    batches = json.loads(request.body.decode())
    done, unsaved_elements = save_scorm_data(attempt,batches)
    return http.JsonResponse({'received_batches':done,'unsaved_elements':unsaved_elements})

