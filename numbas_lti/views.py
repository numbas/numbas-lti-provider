from django.shortcuts import render,redirect
from django.utils.decorators import available_attrs
from django.views.decorators.csrf import csrf_exempt
from django_auth_lti.decorators import lti_role_required
from django_auth_lti.const import LEARNER, INSTRUCTOR
from django_auth_lti.patch_reverse import patch_reverse
from django.views import generic
from django.core.urlresolvers import reverse
from django import http
import json

patch_reverse()

from functools import wraps

from .models import Resource,Exam

# Create your views here.
@csrf_exempt
def index(request):
    is_instructor = 'Instructor' in request.LTI.get('roles')

    context = {
        'title': 'Hi',
        'resource': request.resource,
        'is_instructor': is_instructor,
    }
    return render(request,'numbas_lti/index.html',context)

def view2(request):
    is_instructor = 'Instructor' in request.LTI.get('roles')
    if is_instructor:
        if not request.resource.exam:
            return redirect(reverse('create_exam'))
        else:
            return redirect(reverse('manage_resource',args=(request.resource.pk,)))
    else:
        if not request.resource.exam:
            return render(request,'numbas_lti/exam_not_set_up.html',{})
        else:
            return redirect(reverse('run_exam'))

class CreateExamView(generic.edit.CreateView):
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

class ManageResourceView(generic.detail.DetailView):
    model = Resource
    template_name = 'numbas_lti/manage_resource.html'
    context_object_name = 'resource'

class RunExamView(generic.detail.DetailView):
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
