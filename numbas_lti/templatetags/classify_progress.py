from django.template import Library
from django.template.loader import get_template

register = Library()

@register.filter
def classify_progress(t):
    if t >= 1:
        return 'completed'
    if t > 0.75:
        return 'almost-complete'
    if t == 0:
        return 'not-started'
    return 'in-progress'

@register.filter
def completion_text(status):
    return {
        'not attempted': 'Not started',
        'incomplete': 'In progress',
        'completed': 'Done ✔',
    }[status]

@register.filter
def completion_class(status):
    return {
        'not attempted': '',
        'incomplete': 'info',
        'completed': 'success',
    }[status]

@register.filter
def progress_text(t):
    cls = classify_progress(t)
    return {
        'completed': 'Done ✔',
        'almost-complete': 'Almost complete',
        'in-progress': 'In progress',
        'not-started': 'Not started',
    }[cls]
