from django.template import Library
from django.template.loader import get_template

register = Library()

@register.inclusion_tag('numbas_lti/datetime.html')
def time_tag(t, **kwargs):
    return {
        't': t, 
    }

@register.filter
def time_tag(t):
    template = get_template('numbas_lti/datetime.html')

    return template.render({'t': t}).strip()
