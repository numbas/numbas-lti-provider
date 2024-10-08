from .mixins import HelpLinkMixin, ManagementViewMixin
from django.contrib.auth.mixins import PermissionRequiredMixin, LoginRequiredMixin
from django.contrib.auth.views import redirect_to_login
from django.views import generic
from django.urls import reverse_lazy, reverse

from numbas_lti import forms
from numbas_lti.models import SebSettings

class SebSettingsManagementMixin(PermissionRequiredMixin, LoginRequiredMixin, ManagementViewMixin):
    permission_required = ('numbas_lti.add_sebsettings',)
    login_url = reverse_lazy('login')
    management_tab = 'lockdown'

    def handle_no_permission(self):
        return redirect_to_login(self.request.get_full_path(), self.get_login_url(), self.get_redirect_field_name())

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)

        context['seb_launch_url'] = self.request.build_absolute_uri(reverse('seb_launch'))
        context['seb_quit_url'] = self.request.build_absolute_uri(reverse('seb_quit'))

        return context

class CreateView(HelpLinkMixin, SebSettingsManagementMixin, generic.edit.CreateView):
    model = SebSettings
    template_name = 'numbas_lti/management/admin/seb_settings/create.html'
    form_class = forms.CreateSebSettingsForm
    success_url = reverse_lazy('list_seb_settings')
    helplink = 'admin/lockdown-apps.html#adding-a-safe-exam-browser-settings-file'

class UpdateView(HelpLinkMixin, SebSettingsManagementMixin, generic.edit.UpdateView):
    model = SebSettings
    template_name = 'numbas_lti/management/admin/seb_settings/edit.html'
    form_class = forms.CreateSebSettingsForm
    success_url = reverse_lazy('list_seb_settings')
    helplink = 'admin/lockdown-apps.html#adding-a-safe-exam-browser-settings-file'

class ListView(HelpLinkMixin, SebSettingsManagementMixin, generic.list.ListView):
    model = SebSettings
    template_name = 'numbas_lti/management/admin/seb_settings/list.html'
    helplink = 'admin/lockdown-apps.html#safe-exam-browser'

class DeleteView(HelpLinkMixin, SebSettingsManagementMixin, generic.edit.DeleteView):
    model = SebSettings
    template_name = 'numbas_lti/management/admin/seb_settings/delete.html'
    success_url = reverse_lazy('list_seb_settings')
    helplink = 'admin/lockdown-apps.html#safe-exam-browser'

class QuitView(generic.base.TemplateView):
    template_name = 'numbas_lti/seb_quit.html'
