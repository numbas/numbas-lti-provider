from django import template
from math import floor

register = template.Library()

@register.filter
def percentage(value):
    return "{0:.0%}".format(value)

@register.filter
def percentage_bin(value,bins=3):
    n = floor(value*bins)
    if n==bins:
        n -= 1
    return n
