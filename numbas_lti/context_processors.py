from django.conf import settings
from django.utils.translation import gettext_lazy as _
from . import version

def global_settings(request):
    return {
        'NUMBAS_LTI_VERSION': version,
        'HELP_URL': getattr(settings, 'HELP_URL', f'https://docs.numbas.org.uk/lti/en/'+version+'/'),
        'INSTANCE_NAME': getattr(settings, 'INSTANCE_NAME', _('Unnamed')),
    }
