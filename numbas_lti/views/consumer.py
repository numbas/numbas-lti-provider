from .mixins import ManagementViewMixin, get_lti_entry_url
from django.contrib.auth import login
from django.contrib.auth.mixins import PermissionRequiredMixin, LoginRequiredMixin
from django.contrib.staticfiles.templatetags.staticfiles import static
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils.translation import ugettext_lazy as _
from django.views import generic
from numbas_lti import forms
from numbas_lti.models import LTIConsumer

class ConsumerManagementMixin(PermissionRequiredMixin,LoginRequiredMixin,ManagementViewMixin):
    permission_required = ('numbas_lti.add_lticonsumer',)
    login_url = reverse_lazy('login')
    management_tab = 'consumers'

def get_config_url(request):
    return request.build_absolute_uri(reverse('config_xml',exclude_resource_link_id=True))

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
        context['named_contexts'] = sorted(consumer.contexts.exclude(name='').all(),key=lambda c: c.name.upper())

        return context

