from .mixins import static_view, request_is_instructor, get_lti_entry_url, get_config_url
from numbas_lti.models import LTIConsumer, LTIUserData, LTILaunch
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.staticfiles.templatetags.staticfiles import static
from django.shortcuts import render, redirect
from django_auth_lti.patch_reverse import reverse
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from importlib import import_module
import json
import logging
from ipware import get_client_ip
from urllib.parse import urlparse, urlunparse, parse_qs
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

no_websockets = static_view('numbas_lti/no_websockets.html')
not_authorized = static_view('numbas_lti/not_authorized.html')

@csrf_exempt
def index(request):
    if not User.objects.filter(is_superuser=True).exists():
        return redirect(reverse('create_superuser'))
    context = {
        'entry_url': get_lti_entry_url(request),
    }
    return render(request,'numbas_lti/index.html',context)

@csrf_exempt
def config_xml(request):
    return render(request,
        'numbas_lti/config.xml',
        {
            'entry_url': get_lti_entry_url(request),
            'icon': request.build_absolute_uri(static('icon.png')),
        }, 
        content_type='application/xml' 
    )

def add_query_param(url,extras):
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    for k,v in extras.items():
        if k not in query:
            query[k] = [v]
    url = urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params,
         urlencode(query,doseq=True), parsed.fragment)
    )
    return url
    
@csrf_exempt
def lti_entry(request):
    if request.method != 'POST':
        return not_post(request)

    if request.session.session_key is None:
        request.session.save()
    session_key = request.session.session_key
    return redirect(add_query_param(reverse('check_cookie_entry'),{'session_key':session_key}))

def do_lti_entry(request):
    data = {}
    if hasattr(request,'LTI'):
        lti_message_type = request.LTI.get('lti_message_type')
    else:
        lti_message_type = request.POST.get('lti_message_type')
    if lti_message_type is None:
        return not_an_lti_launch(request)

    launch_types = {
        'basic-lti-launch-request': basic_lti_launch,
        'ToolProxyRegistrationRequest': consumer_registration_request,
    }
    
    if lti_message_type in launch_types:
        return launch_types[lti_message_type](request)
    else:
        return unrecognised_message_type(request)

def check_cookie_entry(request):
    sent_session_key = request.GET.get('session_key')
    resource_link_id = request.GET.get('resource_link_id')
    if sent_session_key == request.session.session_key:
        return do_lti_entry(request)
    else:
        url = add_query_param(reverse('set_cookie_entry'),{'session_key': sent_session_key, 'resource_link_id': resource_link_id})
        return render(request, 'numbas_lti/check_cookie_entry.html',{'url':url})
    
def set_cookie_entry(request):
    session_key = request.GET.get('session_key')
    resource_link_id = request.GET.get('resource_link_id')
    engine = import_module(settings.SESSION_ENGINE)
    request.session = engine.SessionStore(session_key)
    request.session.modified = True
    return redirect(add_query_param(reverse('check_cookie_entry'),{'session_key':session_key, 'resource_link_id': resource_link_id}))
    
def not_post(request):
    return render(request,'numbas_lti/launch_errors/not_post.html',{})

def not_an_lti_launch(request):
    return render(request,'numbas_lti/launch_errors/not_an_lti_launch.html',{'debug':settings.DEBUG, 'post_data': sorted(request.POST.items(),key=lambda x:x[0])})

def basic_lti_launch(request):
    try:
        request.resource
    except AttributeError:
        return no_resource(request)

    consumer = request.resource.context.consumer

    is_instructor = request_is_instructor(request)

    user_id = request.LTI.get('user_id')

    user_data_args = {
        'user': request.user, 
        'resource': request.resource, 
        'consumer': consumer, 
        'consumer_user_id': user_id,
    }
    user_data = LTIUserData.objects.filter(**user_data_args).last()
    if user_data is None:
        user_data = LTIUserData.objects.create(**user_data_args)

    user_data.lis_result_sourcedid = request.LTI.get('lis_result_sourcedid')
    user_data.lis_person_sourcedid = request.LTI.get('lis_person_sourcedid','')
    user_data.lis_outcome_service_url = request.LTI.get('lis_outcome_service_url')
    user_data.is_instructor = is_instructor
    user_data.save()

    ip_address, ip_routable = get_client_ip(request)

    LTILaunch.objects.create(
        user = request.user,
        resource = request.resource,
        user_agent = request.META.get('HTTP_USER_AGENT'),
        ip_address = ip_address
    )

    if is_instructor:
        if not request.resource.exam:
            return redirect(reverse('create_exam',args=(request.resource.pk,)))
        else:
            return redirect(reverse('resource_dashboard',args=(request.resource.pk,)))
    else:
        if not request.resource.exam:
            return render(request,'numbas_lti/exam_not_set_up.html',{})
        else:
            return redirect(reverse('show_attempts'))

@csrf_exempt
def no_resource(request):
    logger.error(_("No resource found for an LTI entry:\n"+json.dumps(request.POST)))
    return render(request,'numbas_lti/launch_errors/no_resource.html',{'debug':settings.DEBUG, 'post_data': sorted(request.POST.items(),key=lambda x:x[0])})

def consumer_registration_request(request):
    return render(request, 'numbas_lti/consumer_registration.html',{'config_url': get_config_url(request)})

def unrecognised_message_type(request, lti_message_type):
    logger.error(_("Unrecognised LTI launch type: {}\n{}".format(lti_message_type,json.dumps(request.POST))))
    return render(request,'numbas_lti/launch_errors/unrecognised_lti_message_type.html',{'debug':settings.DEBUG, 'post_data': sorted(request.POST.items(),key=lambda x:x[0]), 'lti_message_type': lti_message_type})
