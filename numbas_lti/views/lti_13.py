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
from . import mixins, resource
from numbas_lti.backends import new_lti_user
from numbas_lti.models import LTI_13_UserAlias, LTI_13_Consumer, LTIConsumer, LTIContext, Resource, LTI_13_ResourceLink, LTIUserData, LTI_13_Context
import numbas_lti.forms
import numbas_lti.views.entry
from pathlib import PurePath
from pylti1p3.deep_link_resource import DeepLinkResource
from pylti1p3.contrib.django import DjangoOIDCLogin
from pylti1p3.contrib.django.lti1p3_tool_config import DjangoDbToolConf
from pylti1p3.contrib.django.lti1p3_tool_config.dynamic_registration import DjangoDynamicRegistration

INSTANCE_NAME = settings.INSTANCE_NAME
PAGE_TITLE = gettext('{INSTANCE_NAME} Numbas').format(INSTANCE_NAME=INSTANCE_NAME)
PAGE_DESCRIPTION = gettext('The Numbas LTI provider at {INSTANCE_NAME}.').format(INSTANCE_NAME=INSTANCE_NAME)

class RegisterView(TemplateView):
    template_name ='numbas_lti/lti_13/registration/begin.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['register_url'] = self.request.build_absolute_uri(reverse('lti_13:dynamic_registration'))

        return context

class LoginView(mixins.LTI_13_Mixin, View):
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

class LaunchView(mixins.LTI_13_Mixin, TemplateView):
    """
        Handle a launch activity.

        There are several kinds of launch; the kind of launch is given by the message_launch object.
    """
    http_method_names = ['post']

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def authenticate_user(self):
        user = auth.authenticate(self.request)
        if not user:
            raise Exception("Couldn't authenticate?!!")

        auth.login(self.request, user)

    def post(self, request, *args, **kwargs):
        self.authenticate_user()
        lti_context, resource_link_id = self.get_lti_context()

        message_launch = self.get_message_launch()
        launch_id = message_launch.get_launch_id()

        is_instructor = mixins.request_is_instructor(self.request)

        if message_launch.is_resource_launch():
            resource_pk = self.get_custom_param('resource')
            if resource_pk is not None:
                resource = Resource.objects.get(pk=resource_pk)

                resource_link = LTI_13_ResourceLink.objects.update_or_create(
                    resource_link_id=resource_link_id,
                    resource=resource,
                    context=lti_context,
                    defaults={
                        "title": resource.title,
                    }
                )


        if is_instructor:
            if message_launch.is_deep_link_launch():
                return redirect(self.reverse_with_lti('lti_13:deep_link'))
            elif message_launch.is_resource_launch():
                return redirect(self.reverse_with_lti('lti_13:teacher_launch'))
            else:
                return HttpResponseBadRequest("This launch type is not recognised.")
        elif mixins.request_is_student(self.request):
            if message_launch.is_resource_launch():
                return redirect(self.reverse_with_lti('lti_13:student_launch'))
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
            'https://purl.imsglobal.org/spec/lti-ags/scope/lineitem',
            'https://purl.imsglobal.org/spec/lti-ags/scope/result.readonly',
            'https://purl.imsglobal.org/spec/lti-ags/scope/score'
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

class ResourceLaunchView(mixins.LTI_13_Mixin):

    def record_user_data(self, resource_link):
        user = self.request.user

        consumer = resource_link.context.consumer

        user_alias = user.lti_13_aliases.get(consumer=consumer)

        is_instructor = mixins.request_is_instructor(self.request)

        user_data_args = {
            'user': user, 
            'resource': resource_link.resource, 
            'consumer': consumer, 
            'consumer_user_id': user_alias.sub,
        }

        user_data, _ = LTIUserData.objects.update_or_create(**user_data_args, defaults={"is_instructor": is_instructor})


    def get_resource_link(self):
        try:
            message_launch = self.get_message_launch()
            message_launch_data = message_launch.get_launch_data()
            lti_context, resource_link_id = self.get_lti_context()
            return LTI_13_ResourceLink.objects.filter(resource_link_id=resource_link_id, context=lti_context).last()
        except LTI_13_ResourceLink.DoesNotExist:
            return None

class TeacherLaunchView(ResourceLaunchView, View):

    def get(self, request, *args, **kwargs):
        resource_link = self.get_resource_link()

        if resource_link:
            self.record_user_data(resource_link)
            numbas_lti.views.entry.record_launch(request, role='teacher', lti_13_resource_link=resource_link)
            return redirect(self.reverse_with_lti('resource_dashboard', args=(resource_link.resource.pk,)))
        else:
            raise SuspiciousOperation(_("This LTI launch does not have a resource associated with it."))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        message_launch = self.get_message_launch()
        message_launch_data = message_launch.get_launch_data()
        context['message_launch_data'] = message_launch_data

        lti_context, resource_link_id = self.get_lti_context()
        context['lti_context'] = lti_context

        context['resources'] = Resource.objects.filter(lti_13_links__context=lti_context).distinct()

        resource_link_claim = message_launch_data.get('https://purl.imsglobal.org/spec/lti/claim/resource_link')
        title = resource_link_claim.get('title')
        description = resource_link_claim.get('description')
        context['new_resource_form'] = numbas_lti.forms.LTI_13_LinkResourceForm(instance=LTI_13_ResourceLink(resource_link_id=resource_link_id, title=title, description=description, context=lti_context))

        return context

class StudentLaunchView(ResourceLaunchView, View):
    def get(self, request, *args, **kwargs):
        resource_link = self.get_resource_link()
    
        self.record_user_data(resource_link)
        numbas_lti.views.entry.record_launch(request, role='student', lti_13_resource_link=resource_link)
        return numbas_lti.views.entry.student_launch(request, resource_link.resource)

class MustBeDeepLinkMixin(mixins.LTI_13_Mixin):
    def dispatch(self, request, *args, **kwargs):
        message_launch = self.get_message_launch()
        if not message_launch.is_deep_link_launch():
            raise SuspiciousOperation(_("This action can only be performed as part of a deep-link launch."))

        return super().dispatch(request, *args, **kwargs)

class DeepLinkView(MustBeDeepLinkMixin, TemplateView):
    template_name = "numbas_lti/lti_13/deep_link.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        message_launch = self.get_message_launch()
        message_launch_data = message_launch.get_launch_data()
        context['message_launch_data'] = message_launch_data

        resource_link_claim = message_launch_data.get('https://purl.imsglobal.org/spec/lti/claim/resource_link')
        context['resource_link_claim'] = resource_link_claim

        lti_context, _ = self.get_lti_context()
        context['lti_context'] = lti_context

        context['resources'] = Resource.objects.filter(lti_13_links__context=lti_context).distinct()

        return context

def deep_link_response(request, message_launch, resource):
    """
        Return a response which ends the deep-link flow, with a link to the given resource
    """
    launch_url = request.build_absolute_uri(reverse('lti_13:launch'))

    resource = DeepLinkResource()\
        .set_url(launch_url)\
        .set_custom_params({
            'resource': resource.pk,
        })\
        .set_title(resource.exam.title)

    html = message_launch.get_deep_link().output_response_form([resource])
    return HttpResponse(html)

class DeepLinkUseResourceView(MustBeDeepLinkMixin, View):
    http_method_names = ['post',]

    def post(self, *args, **kwargs):
        resource = Resource.objects.get(pk=self.request.POST['resource_pk'])

        message_launch = self.get_message_launch()

        return deep_link_response(self.request, message_launch, resource)

class DeepLinkCreateResourceView(MustBeDeepLinkMixin, resource.CreateExamView):
    def form_valid(self, form):
        exam = self.object = form.save(commit=True)

        resource = Resource.objects.create(title = exam.title, exam=exam)

        message_launch = self.get_message_launch()

        return deep_link_response(self.request, message_launch, resource)
