from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class NumbasLtiConfig(AppConfig):
    name = 'numbas_lti'
    verbose_name = _('Numbas LTI')

    def ready(self):
        import numbas_lti.signals
