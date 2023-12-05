from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _
from pylti1p3.contrib.django.lti1p3_tool_config.apps import PyLTI1p3ToolConfig

class PyLTI1p3ToolConfigBigAutoField(PyLTI1p3ToolConfig):
    default_auto_field = 'django.db.models.BigAutoField'

class NumbasLtiConfig(AppConfig):
    name = 'numbas_lti'
    verbose_name = _('Numbas LTI')

    def ready(self):
        import numbas_lti.signals
