from .mixins import ManagementViewMixin, HelpLinkMixin
from django.contrib.auth.mixins import PermissionRequiredMixin, LoginRequiredMixin
from django.http import JsonResponse
from django.views.generic import CreateView, DetailView, FormView, View, ListView, DeleteView
from django.views.generic.detail import SingleObjectMixin
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from numbas_lti.models import StressTest, Resource, Attempt


class StressTestManagementMixin(HelpLinkMixin, PermissionRequiredMixin,ManagementViewMixin):
    permission_required = ('numbas_lti.add_stresstest',)
    model = StressTest
    login_url = reverse_lazy('login')
    management_tab = 'stress-tests'
    helplink = 'admin/stress-tests.html'

def create_stress_test(request):
    resource = Resource.objects.create(resource_link_id='',title='Stress test')
    stress_test = StressTest.objects.create(resource=resource)
    return redirect(stress_test.get_absolute_url())

class ListStressTestsView(StressTestManagementMixin,ListView):
    template_name = 'numbas_lti/management/admin/stress/index.html'
    model = StressTest

class StressTestView(StressTestManagementMixin,DetailView):
    template_name = 'numbas_lti/management/admin/stress/view.html'
    context_object_name = 'test'

class NewAttemptView(StressTestManagementMixin,SingleObjectMixin,View):

    def post(self, request, *args, **kwargs):
        stresstest = self.get_object()

        attempt = Attempt.objects.create(
            resource=stresstest.resource,
            user=request.user
        )

        return JsonResponse({
            'pk': attempt.pk,
            'fallback_url': reverse('attempt_scorm_data_fallback',args=(attempt.pk,)),
        })

class WipeDataView(StressTestManagementMixin,SingleObjectMixin,View):
    def post(self,request,*args,**kwargs):
        stresstest = self.get_object()
        n,_ = stresstest.resource.attempts.all().delete()
        return JsonResponse({"succeeded":True})

class DeleteStressTestView(StressTestManagementMixin,DeleteView):
    def get_success_url(self):
        return reverse('list_stresstests')
