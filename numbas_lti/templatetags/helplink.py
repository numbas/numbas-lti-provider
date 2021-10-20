from django.template import Library
from django.conf import settings

register = Library()

@register.inclusion_tag('numbas_lti/helplink.html', takes_context=True)
def helplink(context, url, **kwargs):
    return {
        'url': url, 
        'subject': kwargs.get('subject'), 
        'float': kwargs.get('float',True),
        'HELP_URL': context['HELP_URL']
    }

