from django.views import generic
from numbas_lti.models import LTIContext
from .consumer import ConsumerManagementMixin

class ManageContextView(ConsumerManagementMixin, generic.detail.DetailView):
    model = LTIContext
    context_object_name = 'context'
    template_name = 'numbas_lti/management/admin/view_context.html'
