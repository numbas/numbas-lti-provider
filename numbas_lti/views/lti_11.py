from .mixins import request_is_instructor, get_lti_entry_url, get_config_url, reverse_with_lti
from numbas_lti.util import add_query_param
from numbas_lti.models import  LTIUserData, LTI_11_UserData
from .entry import record_launch, student_launch
from django_auth_lti.patch_reverse import reverse
from django.conf import settings
from django.templatetags.static import static
from django.shortcuts import render, redirect
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
import json

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
    
def basic_lti_11_launch(request):
    try:
        request.resource
    except AttributeError:
        return no_resource(request)

    consumer = request.resource.lti_11_contexts().first().consumer

    is_instructor = request_is_instructor(request)

    user_id = request.LTI.get('user_id')

    user_data_args = {
        'user': request.user, 
        'resource': request.resource, 
        'consumer': consumer, 
        'consumer_user_id': user_id,
    }
    user_data, _ = LTIUserData.objects.update_or_create(
        **user_data_args,
        defaults = {
            "is_instructor": is_instructor
        }
    )

    lti_11_data, _ = LTI_11_UserData.objects.update_or_create(
        user_data=user_data,
        defaults = {
            "lis_result_sourcedid": request.LTI.get('lis_result_sourcedid'),
            "lis_person_sourcedid": request.LTI.get('lis_person_sourcedid',''),
            "lis_outcome_service_url": request.LTI.get('lis_outcome_service_url'),
        }
    )

    record_launch(request, role='teacher' if is_instructor else 'student', lti_11_resource_link=request.lti_11_resource_link)

    if is_instructor:
        return redirect(reverse_with_lti(request, 'resource_dashboard',args=(request.resource.pk,)))
    else:
        return student_launch(request, request.resource)

@csrf_exempt
def no_resource(request):
    logger.error(_("No resource found for an LTI entry:\n"+json.dumps(request.POST)))
    return render(request,'numbas_lti/launch_errors/no_resource.html',{'debug':settings.DEBUG, 'post_data': sorted(request.POST.items(),key=lambda x:x[0])})

def consumer_registration_request(request):
    return render(request, 'numbas_lti/consumer_registration.html',{'config_url': get_config_url(request)})

def unrecognised_message_type(request, lti_message_type):
    logger.error(_("Unrecognised LTI launch type: {}\n{}".format(lti_message_type,json.dumps(request.POST))))
    return render(request,'numbas_lti/launch_errors/unrecognised_lti_message_type.html',{'debug':settings.DEBUG, 'post_data': sorted(request.POST.items(),key=lambda x:x[0]), 'lti_message_type': lti_message_type})

def not_post(request):
    return render(request,'numbas_lti/launch_errors/not_post.html',{})

def not_an_lti_launch(request):
    return render(request,'numbas_lti/launch_errors/not_an_lti_launch.html',{'debug':settings.DEBUG, 'post_data': sorted(request.POST.items(),key=lambda x:x[0])})

