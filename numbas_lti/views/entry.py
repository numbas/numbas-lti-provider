from .mixins import static_view, request_is_instructor, get_lti_entry_url, get_config_url
from numbas_lti.models import LTIConsumer, LTIUserData
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.staticfiles.templatetags.staticfiles import static
from django.shortcuts import render, redirect
from django_auth_lti.patch_reverse import reverse
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
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

def not_post(request):
    return render(request,'numbas_lti/launch_errors/not_post.html',{})

def not_an_lti_launch(request):
    return render(request,'numbas_lti/launch_errors/not_an_lti_launch.html',{'debug':settings.DEBUG, 'post_data': sorted(request.POST.items(),key=lambda x:x[0])})

def basic_lti_launch(request):
    try:
        request.resource
    except AttributeError:
        return no_resource(request)

    client_key = request.POST.get('oauth_consumer_key')
    consumer = LTIConsumer.objects.get(key=client_key)

    user_id = request.LTI.get('user_id')

    user_data = LTIUserData.objects.filter(user=request.user, resource = request.resource, consumer=consumer, consumer_user_id = user_id).last()
    if user_data is None:
        user_data = LTIUserData.objects.create(user=request.user, resource = request.resource, consumer=consumer, consumer_user_id = user_id)

    user_data.lis_result_sourcedid = request.POST.get('lis_result_sourcedid')
    user_data.lis_outcome_service_url = request.POST.get('lis_outcome_service_url')
    user_data.save()

    if request_is_instructor(request):
        if not request.resource.exam:
            return redirect(reverse('create_exam',args=(request.resource.pk,)))
        else:
            return redirect(reverse('dashboard',args=(request.resource.pk,)))
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
