from django.conf import settings
from django.utils.translation import gettext_lazy as _
from . import version
from django.urls import reverse

def global_settings(request):
    return {
        'NUMBAS_LTI_VERSION': version,
        'HELP_URL': getattr(settings, 'HELP_URL', f'https://docs.numbas.org.uk/lti/en/'+version+'/'),
        'INSTANCE_NAME': getattr(settings, 'INSTANCE_NAME', _('Unnamed')),
        'SEB_QUIT_LINK': request.build_absolute_uri(reverse('seb_quit', exclude_resource_link_id=True)),
    }
