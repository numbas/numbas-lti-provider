from django import template
from math import floor

register = template.Library()

@register.filter
def percentage(value):
    return "{0:.0%}".format(value)

@register.filter
def percentage_bin(value,bins=3):
    if value==0:
        return 0
    elif value==1:
        return bins-1
    else:
        n = floor(value*(bins-2))+1
    return n
