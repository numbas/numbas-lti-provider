# from https://code.djangoproject.com/ticket/10941#comment:27
from django import template
import collections.abc
from django_auth_lti.patch_reverse import reverse

from django.http import QueryDict

register = template.Library()

def is_iterable(v):
    return isinstance(v, collections.abc.Iterable) and not isinstance(v, str)

@register.simple_tag
def build_query(**kwargs):
    """Build a query string"""
    query_dict = QueryDict(mutable=True)

    for k, v in kwargs.items():
        if is_iterable(v):
            query_dict.setlist(k, v)
        else:
            query_dict[k] = v

    return query_dict.urlencode()


@register.simple_tag(takes_context=True)
def set_query_values(context, **kwargs):
    """Override existing parameters in the current query string"""
    query_dict = context.request.GET.copy()

    for k, v in kwargs.items():
        if is_iterable(v):
            query_dict.setlist(k, v)
        else:
            query_dict[k] = v

    return query_dict.urlencode()


@register.simple_tag(takes_context=True)
def append_query_values(context, **kwargs):
    """Append to existing parameters in the current query string"""
    query_dict = context.request.GET.copy()

    for k, v in kwargs.items():
        if is_iterable(v):
            for v_item in v:
                query_dict.appendlist(k, v_item)
        else:
            query_dict.appendlist(k, v)

    return query_dict.urlencode()

@register.simple_tag(takes_context=True)
def url_with_lti(context, view_name, *args, **kwargs):
    try:
        current_app = context.request.current_app
    except AttributeError:
        try:
            current_app = context.request.resolver_match.namespace
        except AttributeError:
            current_app = None

    try:
        current_app = context.request.current_app
    except AttributeError:
        try:
            current_app = context.request.resolver_match.namespace
        except AttributeError:
            current_app = None

    query_dict = QueryDict(mutable=True)

    if 'lti_13_launch_id' in kwargs:
        query_dict['lti_13_launch_id'] = kwargs.pop('lti_13_launch_id')

    if 'message_launch' in context:
        query_dict['lti_13_launch_id'] = context['message_launch'].get_launch_id()

    url = reverse(view_name, args=args, kwargs=kwargs, current_app=current_app)

    query = query_dict.urlencode()
    if query:
        url += '?' + query
    
    return url
