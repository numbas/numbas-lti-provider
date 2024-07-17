from django.views import generic
from django.db.models import Q
from django.db.models.functions import Lower
from django import http
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.template.loader import get_template
from django.template.response import TemplateResponse
from django_auth_lti.patch_reverse import reverse
from numbas_lti.models import LTIConsumer, LTIContext, Resource
from django.utils.translation import gettext_lazy as _, gettext

def user_json(user):
    resources = Resource.objects.filter(launches__user=user)
    contexts = LTIContext.objects.filter(Q(lti_13_resource_links__resource__in=resources) | Q(lti_11_resource_links__resource__in=resources))
    consumers = LTIConsumer.objects.filter(contexts__in=contexts).distinct()
    return {
        'model': 'user',
        'id': user.pk,
        'label': get_template('numbas_lti/management/search/autocomplete_user.html').render({'user': user, 'consumers': [c.title for c in consumers]}),
        'url': reverse('global_user_info', args=(user.pk,)),
    }

def context_json(context):
    return {
        'model': 'context',
        'id': context.pk,
        'label': context.label,
        'label': get_template('numbas_lti/management/search/autocomplete_context.html').render({'context': context}),
        'url': context.get_absolute_url(),
    }

def resource_json(resource):
    return {
        'model': 'resource',
        'id': resource.pk,
        'label': get_template('numbas_lti/management/search/autocomplete_resource.html').render({'resource': resource}),
        'url': reverse('resource_dashboard',args=(resource.pk,)),
    }

def find_users(words):
    user_q = Q()
    for word in words:
        user_q &= (Q(first_name__icontains=word) | Q(last_name__icontains=word))

    query = ' '.join(words)
    user_q |= Q(username__icontains=query)
    user_q |= Q(email__icontains=query)

    users = User.objects.filter(user_q).distinct().order_by(Lower('first_name'), Lower('last_name'))
    return users

def find_contexts(words):
    context_q = Q()
    for word in words:
        context_q &= (Q(name__icontains=word) | Q(label__icontains=word))

    contexts = LTIContext.objects.filter(context_q).distinct().order_by(Lower('name'), 'consumer')
    return contexts

def find_resources(words):
    resource_q = Q()
    for word in words:
        resource_q &= (Q(title__icontains=word) | Q(exam__title__icontains=word))

    resources = Resource.objects.filter(resource_q).distinct().order_by(Lower('title'), Lower('exam__title'))
    return resources

def may_global_search(user):
    return user.is_superuser

@user_passes_test(may_global_search)
def search_autocomplete(request):
    query = request.GET.get('query','')

    if not query.strip():
        return http.JsonResponse({'results': []})
    
    words = [x.lower().strip() for x in query.split(' ')]

    offset = 0
    max_hits = 5

    users_json = [user_json(user) for user in find_users(words)[offset:offset+max_hits]]
    contexts_json = [context_json(context) for context in find_contexts(words)[offset:offset+max_hits]]
    resources_json = [resource_json(resource) for resource in find_resources(words)[offset:offset+max_hits]]

    results = users_json + contexts_json + resources_json
    return http.JsonResponse({'results': results})

@user_passes_test(may_global_search)
def global_search(request):
    query = request.GET.get('query','')

    model = request.GET.get('model','users')

    page = int(request.GET.get('page','0'))
    per_page = 20
    offset = per_page * page

    if not query.strip():
        results = []
        num_results = 0
        users = User.objects.none()
        resources = Resource.objects.none()
        contexts = LTIContext.objects.none()
    else:
        words = [x.lower().strip() for x in query.split(' ')]

        users = find_users(words)
        contexts = find_contexts(words)
        resources = find_resources(words)

        if not request.GET.get('model'):
            if users.exists():
                model = 'users'
            elif contexts.exists():
                model = 'contexts'
            elif resources.exists():
                model = 'resources'
            else:
                model = 'users'

    if model=='users':
        results = users
    elif model=='contexts':
        results = contexts
    elif model=='resources':
        results = resources

    num_results = results.count()
    results = results[offset:offset+per_page]


    if model=='users':
        single_model = _('user')
    elif model=='contexts':
        single_model = _('context')
    elif model=='resources':
        single_model = _('resource')

    context = {
        'global_search_query': query,
        'num_results': num_results,
        'results': results,
        'global_search_model': model,
        'single_model': single_model,
        'models': _(model),
        'users': users,
        'contexts': contexts,
        'resources': resources,
        'page': page,
        'per_page': per_page,
        'management_tab': 'dashboard',
        'has_prev_page': page > 0,
        'has_next_page': (offset+per_page) < num_results,
        'start': offset+1,
        'end': min(num_results,offset+per_page),
    }

    return TemplateResponse(request=request, template='numbas_lti/management/admin/global_search.html', context=context)
