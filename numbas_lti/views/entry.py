from .mixins import static_view, request_is_instructor, get_lti_entry_url, get_config_url, reverse_with_lti
from numbas_lti import lockdown_app
from numbas_lti.util import add_query_param
from numbas_lti.models import LTIConsumer, LTIUserData, LTI_11_UserData, LTILaunch
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
import re

logger = logging.getLogger(__name__)

no_websockets = static_view('numbas_lti/no_websockets.html')
not_authorized = static_view('numbas_lti/not_authorized.html')

@csrf_exempt
def css_test(request):
    if not User.objects.filter(is_superuser=True).exists():
        return redirect(reverse('create_superuser'))
    context = {}
    return render(request,'numbas_lti/css_test.html',context)

@csrf_exempt
def index(request):
    if not User.objects.filter(is_superuser=True).exists():
        return redirect(reverse('create_superuser'))
    context = {}
    return render(request,'numbas_lti/index.html',context)

def set_cookie_entry(request):
    session_key = request.GET.get('session_key')
    engine = import_module(settings.SESSION_ENGINE)
    request.session = engine.SessionStore(session_key)
    request.session.modified = True
    rotate_token(request)
    response = redirect(add_query_param(reverse('check_cookie_entry'),request.GET))

    lti1p3_session_id = request.GET.get('lti1p3-session-id')
    if lti1p3_session_id:
        response.set_cookie('lti1p3-session-id', value=lti1p3_session_id, max_age=3600, secure=request.is_secure(), httponly='True', path='/', samesite='None')

    return response

def check_cookie_entry(request):
    sent_session_key = request.GET.get('session_key')
    resource_link_id = request.GET.get('resource_link_id')
    if sent_session_key == request.session.session_key:
        return do_lti_entry(request)
    else:
        url = add_query_param(reverse('set_cookie_entry'),{'session_key': sent_session_key, 'resource_link_id': resource_link_id})
        return render(request, 'numbas_lti/check_cookie_entry.html',{'url':url})

def do_lti_entry(request):
    from numbas_lti.views import lti_11, lti_13

    if hasattr(request, 'lti_13_message_launch'):
        return lti_13.do_lti_entry(request)
    else:
        return lti_11.do_lti_entry(request)

def record_launch(request, role='', lti_11_resource_link=None, lti_13_resource_link=None):
    ip_address, _ = get_client_ip(request)

    user_agent = request.META.get('HTTP_USER_AGENT')

    resource = None

    if lti_11_resource_link is not None:
        resource = lti_11_resource_link.resource

    if lti_13_resource_link is not None:
        resource = lti_13_resource_link.resource

    launch = LTILaunch.objects.create(
        user = request.user,
        resource = resource,
        user_agent = user_agent,
        ip_address = ip_address,
        role = role,
        lti_11_resource_link = lti_11_resource_link,
        lti_13_resource_link = lti_13_resource_link
    )


def student_launch(request, resource):
    is_instructor = request_is_instructor(request)

    if not resource.exam:
        return render(request,'numbas_lti/exam_not_set_up.html',{})

    controller = lockdown_app.lockdown_app_controller(request)
    if not controller.is_lockdown_app():
        return controller.show_lockdown_link()

    controller = lockdown_app.lockdown_app_controller(request)
    try:
        controller.check_version()
    except lockdown_app.OldVersionException as err:
        return controller.old_version_response(err)

    if not resource.exam:
        return render(request,'numbas_lti/exam_not_set_up.html',{})
    else:
        return redirect(reverse_with_lti(request, 'show_attempts'))

def lockdown_launch(request):
    return redirect(add_query_param(reverse('set_cookie_entry'), request.GET))

def seb_launch(request):
    session_key = request.GET.get('session_key')

    if session_key is None:
        if request.headers.get('X-Safeexambrowser-Configkeyhash'):
            return render(request, 'numbas_lti/launch_errors/seb_launch_without_params.html')

        return render(request, 'numbas_lti/launch_errors/not_seb_launch.html')

    return redirect(add_query_param(reverse('set_cookie_entry'), request.GET))


"""
TODO:

    * Check version numbers on the iOS and Android Numbas apps
    * Check how SEB puts its version number in the user agent
"""
