from .mixins import static_view, request_is_instructor, get_lti_entry_url, get_config_url, reverse_with_lti
from numbas_lti import lockdown_app
from numbas_lti.util import add_query_param
from numbas_lti.models import LTIConsumer, LTIUserData, LTILaunch
from django_auth_lti.patch_reverse import reverse
from django.conf import settings
from django.contrib.auth.models import User
from django.middleware.csrf import rotate_token
from django.templatetags.static import static
from django.shortcuts import render, redirect
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from importlib import import_module
from ipware import get_client_ip
import json
import logging

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

@csrf_exempt
def lti_entry(request):
    if request.method != 'POST':
        return not_post(request)

    if request.session.session_key is None:
        request.session.save()
    session_key = request.session.session_key
    return render(request, 'numbas_lti/debug.html', {})
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
        'basic-lti-launch-request': basic_lti_11_launch,
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
    rotate_token(request)
    return redirect(add_query_param(reverse('check_cookie_entry'),{'session_key':session_key, 'resource_link_id': resource_link_id}))
    
def not_post(request):
    return render(request,'numbas_lti/launch_errors/not_post.html',{})

def not_an_lti_launch(request):
    return render(request,'numbas_lti/launch_errors/not_an_lti_launch.html',{'debug':settings.DEBUG, 'post_data': sorted(request.POST.items(),key=lambda x:x[0])})

def basic_lti_11_launch(request):
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

    record_launch(request, request.resource)

    if is_instructor:
        return redirect(reverse('resource_dashboard',args=(request.resource.pk,)))
    else:
        return student_launch(request, request.resource)

def record_launch(request, resource):
    ip_address, _ = get_client_ip(request)

    user_agent = request.META.get('HTTP_USER_AGENT')

    launch = LTILaunch.objects.create(
        user = request.user,
        resource = resource,
        user_agent = user_agent,
        ip_address = ip_address
    )


def student_launch(request, resource):
    is_instructor = request_is_instructor(request)

    if resource.require_lockdown_app=='numbas' and not lockdown_app.is_lockdown_app(request):
        return show_lockdown_app(request)

    if resource.require_lockdown_app=='seb' and not lockdown_app.is_seb(request):
        return show_seb_link(request)

    if not resource.exam:
        return render(request,'numbas_lti/exam_not_set_up.html',{})
    else:
        return redirect(reverse_with_lti(request, 'show_attempts'))

def show_lockdown_app(request):
    lockdown_url = lockdown_app.make_link(request)
    return render(request, 'numbas_lti/lockdown_launch/numbas_app_link.html', {'lockdown_url': lockdown_url, 'install_url': settings.LOCKDOWN_APP.get('install_url')})

def lockdown_launch(request):
    session_key = request.GET.get('session_key')
    resource_link_id = request.GET.get('resource_link_id')
    return redirect(add_query_param(reverse('set_cookie_entry'), {'resource_link_id': resource_link_id, 'session_key': session_key}))

def show_seb_link(request):
    seb_url = lockdown_app.make_seb_link(request)
    return render(request, 'numbas_lti/lockdown_launch/seb_link.html', {'seb_url': seb_url, 'install_url': settings.LOCKDOWN_APP.get('seb_install_url')})

def seb_launch(request):
    session_key = request.GET.get('session_key')
    resource_link_id = request.GET.get('resource_link_id')

    if session_key is None or resource_link_id is None:
        return render(request, 'numbas_lti/launch_errors/not_seb_launch.html')

    return redirect(add_query_param(reverse('set_cookie_entry'), {'resource_link_id': resource_link_id, 'session_key': session_key}))

@csrf_exempt
def no_resource(request):
    logger.error(_("No resource found for an LTI entry:\n"+json.dumps(request.POST)))
    return render(request,'numbas_lti/launch_errors/no_resource.html',{'debug':settings.DEBUG, 'post_data': sorted(request.POST.items(),key=lambda x:x[0])})

def consumer_registration_request(request):
    return render(request, 'numbas_lti/consumer_registration.html',{'config_url': get_config_url(request)})

def unrecognised_message_type(request, lti_message_type):
    logger.error(_("Unrecognised LTI launch type: {}\n{}".format(lti_message_type,json.dumps(request.POST))))
    return render(request,'numbas_lti/launch_errors/unrecognised_lti_message_type.html',{'debug':settings.DEBUG, 'post_data': sorted(request.POST.items(),key=lambda x:x[0]), 'lti_message_type': lti_message_type})
