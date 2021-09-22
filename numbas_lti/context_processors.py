from django.conf import settings
from django.utils.translation import gettext_lazy as _

def version(request):
    return {
        'NUMBAS_LTI_VERSION': 'v3.0',
    }

def global_settings(request):
    return {
            'HELP_URL': getattr(settings, 'HELP_URL', 'https://docs.numbas.org.uk/lti'),
            'INSTANCE_NAME': getattr(settings, 'INSTANCE_NAME', _('Unnamed')),
    }
