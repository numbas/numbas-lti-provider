from .mixins import HelpLinkMixin, ManagementViewMixin, get_lti_entry_url, get_config_url
from django.contrib.auth import login
from django.contrib.auth.mixins import PermissionRequiredMixin, LoginRequiredMixin
from django.contrib.auth.views import redirect_to_login
from django.templatetags.static import static
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django_auth_lti.patch_reverse import reverse
from django.utils.translation import gettext_lazy as _
from django.views import generic
from numbas_lti import forms
from numbas_lti.models import LTIConsumer, ConsumerTimePeriod

class ConsumerManagementMixin(PermissionRequiredMixin,LoginRequiredMixin,ManagementViewMixin):
    permission_required = ('numbas_lti.add_lticonsumer',)
    login_url = reverse_lazy('login')
    management_tab = 'consumers'

    def handle_no_permission(self):
        return redirect_to_login(self.request.get_full_path(), self.get_login_url(), self.get_redirect_field_name())

class ListConsumersView(HelpLinkMixin, ConsumerManagementMixin, generic.list.ListView):
    model = LTIConsumer
    template_name = 'numbas_lti/management/admin/consumer/list.html'
    helplink = 'admin/consumers.html'

class CreateConsumerView(HelpLinkMixin, ConsumerManagementMixin, generic.edit.CreateView):
    model = LTIConsumer
    template_name = 'numbas_lti/management/admin/consumer/create.html'
    form_class = forms.CreateConsumerForm
    success_url = reverse_lazy('list_consumers')
    helplink = 'admin/consumers.html#adding-a-consumer'

class DeleteConsumerView(ConsumerManagementMixin,generic.edit.DeleteView):
    model = LTIConsumer
    context_object_name = 'consumer'
    template_name = 'numbas_lti/management/admin/consumer/confirm_delete.html'
    success_url = reverse_lazy('list_consumers')

    def form_valid(self,form):
        consumer = self.get_object()
        consumer.deleted = True
        consumer.save()

        return redirect(self.get_success_url())

class ManageConsumerView(HelpLinkMixin, ConsumerManagementMixin,generic.detail.DetailView):
    model = LTIConsumer
    context_object_name = 'consumer'
    template_name = 'numbas_lti/management/admin/consumer/view.html'
    helplink = 'admin/consumers.html#managing-a-consumer'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args,**kwargs)
        
        consumer = self.get_object()

        context['entry_url'] = get_lti_entry_url(self.request)
        context['config_url'] = get_config_url(self.request)
        context['icon_url'] = self.request.build_absolute_uri(static('icon.png'))

        context['unnamed_contexts'] = consumer.contexts.filter(name='').all()
        context['named_contexts'] = sorted(consumer.contexts.exclude(name='').all(),key=lambda c: c.name.upper())
        context['period_groups'] = consumer.contexts_grouped_by_period()

        return context

class ManageTimePeriodsView(HelpLinkMixin, ConsumerManagementMixin,generic.edit.UpdateView):
    model = LTIConsumer
    context_object_name = 'consumer'
    template_name = 'numbas_lti/management/admin/consumer/manage_time_periods.html'
    form_class = forms.ConsumerTimePeriodFormSet
    helplink = 'admin/consumers.html#time-periods'
    
    def get_success_url(self):
        return reverse('view_consumer',args=(self.get_object().pk,))

class DeleteTimePeriodView(ConsumerManagementMixin,generic.edit.DeleteView):
    model = ConsumerTimePeriod

    def get(self,*args,**kwargs):
        return self.post(*args,**kwargs)
    
    def get_success_url(self):
        return reverse('consumer_manage_time_periods',args=(self.get_object().consumer.pk,))
