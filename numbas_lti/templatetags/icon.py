from django.template import Library
from django.conf import settings

register = Library()

@register.inclusion_tag('numbas_lti/icon.html')
def icon(name, small=False, **kwargs):
    return {
        'name': name, 
        'small': small
    }

