from django.conf import settings
from django.contrib import auth
from django.contrib.auth import get_user_model
from django.core.exceptions import SuspiciousOperation
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseBadRequest, JsonResponse
from django.shortcuts import render, redirect
from django.views import View
from django.views.generic import TemplateView, FormView, RedirectView
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _, gettext
from . import mixins
from numbas_lti.backends import new_lti_user
from numbas_lti.models import LTI_13_UserAlias, LTI_13_Consumer, LTIConsumer, LTIContext, Resource, LTI_13_ResourceLink
import numbas_lti.forms
from pathlib import PurePath
from pylti1p3.contrib.django import DjangoOIDCLogin
from pylti1p3.contrib.django.lti1p3_tool_config import DjangoDbToolConf
from pylti1p3.contrib.django.lti1p3_tool_config.dynamic_registration import DjangoDynamicRegistration

INSTANCE_NAME = settings.INSTANCE_NAME
PAGE_TITLE = gettext('{INSTANCE_NAME} Numbas').format(INSTANCE_NAME=INSTANCE_NAME)
PAGE_DESCRIPTION = gettext('The Numbas LTI provider at {INSTANCE_NAME}.').format(INSTANCE_NAME=INSTANCE_NAME)

class LTIView(mixins.LTI_13_Mixin, mixins.LTI_13_Only_Mixin):
    pass

class CachedLTIView(mixins.CachedLTI_13_Mixin, mixins.LTI_13_Only_Mixin):
    pass

class IndexView(TemplateView):
    template_name ='numbas_lti/lti_13/index.html'

class RegisterView(TemplateView):
    template_name ='numbas_lti/lti_13/registration/begin.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['register_url'] = self.request.build_absolute_uri(reverse('lti_13:dynamic_registration'))

        return context

class LoginView(LTIView, View):
    """
        LTI login: verify the credentials, and redirect to the target link URI given in the launch parameters.
        The OIDCLogin object handles checking that cookies can be set.
    """
    http_method_names = ['post', 'get']

    def get_launch_url(self):
        """
            Get the intended launch URL during a login request.
        """

        target_link_uri = self.request.POST.get('target_link_uri', self.request.GET.get('target_link_uri'))
        if not target_link_uri:
            raise Exception('Missing "target_link_uri" param')
        return target_link_uri

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        oidc_login = DjangoOIDCLogin(request, self.tool_conf, launch_data_storage = self.launch_data_storage)
        target_link_uri = self.get_launch_url()
        return oidc_login\
            .enable_check_cookies()\
            .redirect(target_link_uri)

class LaunchView(LTIView, TemplateView):
    """
        Handle a launch activity.

        There are several kinds of launch; the kind of launch is given by the message_launch object.
    """
    http_method_names = ['post']

    def authenticate_user(self):
        user = auth.authenticate(self.request)
        if not user:
            raise Exception("Couldn't authenticate?!!")

        auth.login(self.request, user)

    def post(self, request, *args, **kwargs):
        self.authenticate_user()
        self.get_lti_context()

        launch_id = self.message_launch.get_launch_id()

        if self.message_launch.check_teacher_access() or self.message_launch.check_teaching_assistant_access() or self.message_launch.check_staff_access():
            if self.message_launch.is_deep_link_launch():
                return redirect(reverse('lti_13:deep_link', args=(launch_id,)))
            elif self.message_launch.is_resource_launch():
                return redirect(reverse('lti_13:teacher_launch', args=(launch_id,)))
            else:
                return HttpResponseBadRequest("This launch type is not recognised.")
        elif self.message_launch.check_student_access():
            if self.message_launch.is_resource_launch():
                return redirect(reverse('lti_13:student_launch', args=(launch_id,)))
            else:
                return HttpResponseBadRequest("This launch type is not recognised.")
        else:
            return HttpResponseBadRequest(f"You have an unknown role.")

class JWKSView(View):
    """
        Return the tool's JSON Web Key Set.
    """
    tool_conf = DjangoDbToolConf()
    def get(self, request, *args, **kwargs):
        return JsonResponse(self.tool_conf.get_jwks(), safe=False)

class DynamicRegistration(DjangoDynamicRegistration):
    """
        Dynamic registration handler.
    """
    client_name = PAGE_TITLE
    description = PAGE_DESCRIPTION
    logo_file = 'icon.png'

    initiate_login_url = reverse_lazy('lti_13:login')
    jwks_url = reverse_lazy('lti_13:jwks')
    launch_url = reverse_lazy('lti_13:launch')

    def get_claims(self):
        return ['iss', 'sub', 'name']

    def get_scopes(self):
        return [
            'https://purl.imsglobal.org/spec/lti-nrps/scope/contextmembership.readonly',
        ]

    def get_messages(self):
        return [{
            'type': 'LtiDeepLinkingRequest',
            'target_link_uri': self.request.build_absolute_uri(reverse('lti_13:launch')),
            'label': 'New tool link',
        }]

def register_dynamic(request):
    """
        Dynamic registration view.
        Triggers the dynamic registration handler, which creates an LtiTool entry in the database.
        Returns a page which does a JavaScript postMessage call to the platform to tell it that registration is complete.
    """

    registration = DynamicRegistration(request)

    lti_tool = registration.register()

    consumer = LTIConsumer.objects.create()

    LTI_13_Consumer.objects.create(consumer=consumer, tool=lti_tool)

    return HttpResponse(registration.complete_html())

class TeacherLaunchView(CachedLTIView, TemplateView):
    template_name ='numbas_lti/lti_13/teacher_launch.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        lti_tool = context['lti_tool'] = self.get_lti_tool()
        message_launch_data = self.message_launch.get_launch_data()
        context['message_launch_data'] = message_launch_data

        resource_link_claim = message_launch_data.get('https://purl.imsglobal.org/spec/lti/claim/resource_link')
        context['resource_link_claim'] = resource_link_claim

        lti_context = context['lti_context'] = self.get_lti_context()

        context['resources'] = Resource.objects.filter(lti_13_links__context=lti_context).distinct()

        resource_link_id = resource_link_claim.get('id')
        title = resource_link_claim.get('title')
        description = resource_link_claim.get('description')
        context['new_resource_form'] = numbas_lti.forms.LTI_13_CreateResourceForm(instance=LTI_13_ResourceLink(resource_link_id=resource_link_id, title=title, description=description, context=lti_context))


        return context

class StudentLaunchView(CachedLTIView, RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        return '/'


class DeepLinkView(CachedLTIView, TemplateView):
    template_name = "numbas_lti/lti_13/deep_link.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        lti_tool = context['lti_tool'] = self.get_lti_tool()
        message_launch_data = self.message_launch.get_launch_data()
        context['message_launch_data'] = message_launch_data

        resource_link_claim = message_launch_data.get('https://purl.imsglobal.org/spec/lti/claim/resource_link')
        context['resource_link_claim'] = resource_link_claim

        context['lti_context'] = self.get_lti_context()

        return context

