from django.views import generic
from numbas_lti.models import LTIContext
from .consumer import ConsumerManagementMixin
from django.urls import reverse

class ManageContextView(ConsumerManagementMixin, generic.detail.DetailView):
    model = LTIContext
    context_object_name = 'context'
    template_name = 'numbas_lti/management/admin/context/view.html'

class DeleteContextView(ConsumerManagementMixin, generic.DeleteView):
    model = LTIContext
    context_object_name = 'context'
    template_name = 'numbas_lti/management/admin/context/confirm_delete.html'

    def get_success_url(self):
        return reverse('view_consumer', args=(self.object.consumer.pk,))
