from django.conf import settings
from django.contrib import auth
from django.contrib.auth import get_user_model
from django.core.exceptions import SuspiciousOperation
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseBadRequest, JsonResponse, HttpResponseNotAllowed, Http404
from django.shortcuts import render, redirect
from django.template import loader
from django.templatetags.static import static
from django.views import View, generic
from django.views.generic import TemplateView, FormView, RedirectView, edit, detail
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _, gettext
from . import mixins, resource
from .consumer import ConsumerManagementMixin
from numbas_lti.backends import new_lti_user
from numbas_lti.models import LTI_13_Consumer, LTIConsumer, Resource, LTI_13_ResourceLink, LTI_11_ResourceLink, LTIUserData, LTIConsumerRegistrationToken
import numbas_lti.forms
import numbas_lti.views.entry
from pathlib import PurePath
from pylti1p3.deep_link_resource import DeepLinkResource
from pylti1p3.contrib.django import DjangoOIDCLogin
from pylti1p3.contrib.django.lti1p3_tool_config import DjangoDbToolConf
from pylti1p3.contrib.django.lti1p3_tool_config.dynamic_registration import DjangoDynamicRegistration
from pylti1p3.contrib.django.lti1p3_tool_config.models import LtiTool
from pylti1p3.exception import LtiException
import urllib.parse

INSTANCE_NAME = settings.INSTANCE_NAME
PAGE_TITLE = gettext('{INSTANCE_NAME} Numbas').format(INSTANCE_NAME=INSTANCE_NAME)
PAGE_DESCRIPTION = gettext('The Numbas LTI provider at {INSTANCE_NAME}.').format(INSTANCE_NAME=INSTANCE_NAME)

class RegisterView(mixins.HelpLinkMixin, ConsumerManagementMixin, TemplateView):
    template_name ='numbas_lti/lti_13/registration/begin.html'
    helplink = 'admin/consumers/lti_13.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['launch_url'] = self.request.build_absolute_uri(reverse('lti_13:launch'))
        context['jwks_url'] = self.request.build_absolute_uri(reverse('lti_13:jwks'))
        context['login_url'] = self.request.build_absolute_uri(reverse('lti_13:login'))
        context['icon_url'] = self.request.build_absolute_uri(static("icon.png"))

        return context

def canvas_config_json(request):
    icon_url = request.build_absolute_uri(static("icon.png"))

    iss = request.GET.get('iss','https://canvas.instructure.com')
    platform = urllib.parse.urlparse(iss).netloc
    iss = urllib.parse.quote_plus(iss)

    selection_width, selection_height = (800, 800)

    config = {
        "title": "Numbas",
        "description": _("Numbas assessments"),
        "oidc_initiation_url": request.build_absolute_uri(reverse('lti_13:login')),
        "target_link_uri": request.build_absolute_uri(reverse('lti_13:launch')),
        "custom_fields": {},
        "scopes": [
            'https://purl.imsglobal.org/spec/lti-nrps/scope/contextmembership.readonly',
            'https://purl.imsglobal.org/spec/lti-ags/scope/lineitem',
            'https://purl.imsglobal.org/spec/lti-ags/scope/result.readonly',
            'https://purl.imsglobal.org/spec/lti-ags/scope/score'
        ],
        "extensions": [
            {
                "domain": request.get_host(),
                "tool_id": "numbas_lti_13",
                "privacy_level": "public",
                "platform": platform,
                "settings": {
                    "text": "Numbas",
                    "icon_url": icon_url,
                    "platform": platform,
                    "placements":[
                        {
                            "text": "Numbas",
                            "enabled": True,
                            "icon_url": icon_url,
                            "placement": "editor_button",
                            "message_type": "LtiDeepLinkingRequest",
                            "target_link_uri": request.build_absolute_uri(reverse('lti_13:launch')),
                            "canvas_icon_class": "icon-lti",
                            "selection_width": selection_width,
                            "selection_height": selection_height,
                        },
                        {
                            "text": "Numbas",
                            "enabled": True,
                            "icon_url": icon_url,
                            "placement": "link_selection",
                            "message_type": "LtiDeepLinkingRequest",
                            "target_link_uri": request.build_absolute_uri(reverse('lti_13:launch')),
                            "canvas_icon_class": "icon-lti",
                            "selection_width": selection_width,
                            "selection_height": selection_height,
                        },
                        {
                            "placement": "assignment_selection",
                            "text": "Numbas",
                            "enabled": True,
                            "message_type": "LtiDeepLinkingRequest",
                            "selection_width": selection_width,
                            "selection_height": selection_height,
                        }
                    ]
                }
            }
        ],
        "public_jwk_url": request.build_absolute_uri(reverse('lti_13:jwks'))+"?iss="+iss,
        "public_jwk": {},
    }
    return JsonResponse(config)

class CanvasRegistrationView(ConsumerManagementMixin, edit.CreateView):
    form_class = numbas_lti.forms.CanvasLti13RegistrationForm
    model = LTIConsumer
    template_name = 'numbas_lti/lti_13/registration/canvas.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['email_address'] = settings.DEFAULT_FROM_EMAIL
        context['launch_url'] = self.request.build_absolute_uri(reverse('lti_13:launch'))
        context['canvas_config_url'] = self.request.build_absolute_uri(reverse_lazy('lti_13:canvas_config_json'))
        context['canvas_presets'] = settings.CANVAS_LTI_13_PRESETS

        return context

    def form_valid(self, form):
        data = form.cleaned_data

        tool = register_lti_13_tool(**data)

        consumer = LTIConsumer.objects.create()
        lti_13_consumer = LTI_13_Consumer.objects.create(consumer=consumer, tool=tool)

        return redirect(consumer.get_absolute_url())

class BlackboardRegistrationView(ConsumerManagementMixin, generic.FormView):
    form_class = numbas_lti.forms.BlackboardLti13RegistrationForm
    template_name = 'numbas_lti/lti_13/registration/blackboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['launch_url'] = self.request.build_absolute_uri(reverse('lti_13:launch'))
        context['jwks_url'] = self.request.build_absolute_uri(reverse('lti_13:jwks'))
        context['login_url'] = self.request.build_absolute_uri(reverse('lti_13:login'))
        context['icon_url'] = self.request.build_absolute_uri(static("icon.png"))


        return context

    def form_valid(self, form):
        client_id = form.cleaned_data['client_id']
        deployment_id = form.cleaned_data['deployment_id']
        tool = form.cleaned_data['tool']

        if deployment_id not in tool.deployment_ids:
            tool.deployment_ids.append(deployment_id)
            tool.save(update_fields=('deployment_ids',))

        try:
            lti_13_consumer = LTI_13_Consumer.objects.get(tool=tool)
            consumer = lti_13_consumer.consumer
        except LTI_13_Consumer.DoesNotExist:
            consumer = LTIConsumer.objects.create()
            lti_13_consumer = LTI_13_Consumer.objects.create(consumer=consumer, tool=tool)
    
        return redirect(consumer.get_absolute_url())

class GenericRegistrationView(ConsumerManagementMixin, TemplateView):
    template_name = 'numbas_lti/lti_13/registration/generic.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['launch_url'] = self.request.build_absolute_uri(reverse('lti_13:launch'))
        context['jwks_url'] = self.request.build_absolute_uri(reverse('lti_13:jwks'))
        context['login_url'] = self.request.build_absolute_uri(reverse('lti_13:login'))
        context['icon_url'] = self.request.build_absolute_uri(static("icon.png"))


        return context

    def form_valid(self, form):
        pass

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
            raise Exception('The "target_link_uri" parameter is missing.')
        return target_link_uri

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        try:
            oidc_login = DjangoOIDCLogin(request, self.tool_conf, launch_data_storage = self.launch_data_storage)
            target_link_uri = self.get_launch_url()
            return oidc_login\
                .enable_check_cookies()\
                .redirect(target_link_uri)
        except Exception as e:
            return render(request, 'numbas_lti/launch_errors/login_error.html', {'error': e})

class LaunchView(mixins.LTI_13_Mixin, TemplateView):
    """
        Handle a launch activity.

        There are several kinds of launch; the kind of launch is given by the message_launch object.
    """
    http_method_names = ['post']

    must_have_message_launch = True

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def http_method_not_allowed(self, request, *args, **kwargs):
        return render(request, '405.html', {'allowed_methods': self.http_method_names}, status=405)

    def authenticate_user(self):
        user = auth.authenticate(self.request)
        if not user:
            raise Exception(_("Your login credentials were not valid."))

        auth.login(self.request, user)

    def post(self, request, *args, **kwargs):
        try:
            self.authenticate_user()
        except Exception as e:
            return render(self.request, 'numbas_lti/launch_errors/login_error.html', {'error': e})

        return self.do_lti_entry()

    def do_lti_entry(self):

        lti_context, resource_link_id = self.get_lti_context()

        message_launch = self.get_message_launch()
        launch_id = message_launch.get_launch_id()

        is_instructor = mixins.request_is_instructor(self.request)
        

        if message_launch.is_resource_launch():
            resource_pk = self.get_custom_param('resource')
            if resource_pk is not None:
                resource = Resource.objects.get(pk=resource_pk)

                launch_data = message_launch.get_launch_data()
                resource_link_claim = launch_data.get("https://purl.imsglobal.org/spec/lti/claim/resource_link", {})

                title = resource_link_claim.get('title', resource.title)

                resource_link, _ = LTI_13_ResourceLink.objects.update_or_create(
                    resource_link_id=resource_link_id,
                    resource=resource,
                    context=lti_context,
                    defaults={
                        "title": title,
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

class CreateRegistrationTokenView(edit.CreateView):
    model = LTIConsumerRegistrationToken
    template_name = 'numbas_lti/lti_13/registration/create_token.html'
    form_class = numbas_lti.forms.CreateRegistrationTokenForm

    def get_initial(self):
        platform_name = self.request.GET.get('platform', '')
        return {
            'name': platform_name,
        }


    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)

        context['platform_name'] = self.request.GET.get('platform')
        return context

class RegistrationTokenView(detail.DetailView):
    model = LTIConsumerRegistrationToken
    context_object_name = 'token'
    template_name = 'numbas_lti/lti_13/registration/view_token.html'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)

        token = self.get_object()
        context['registration_url'] = self.request.build_absolute_uri(reverse('lti_13:use_dynamic_registration_token', kwargs={'pk': token.uid,}))
        
        return context

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

class UseRegistrationTokenView(edit.DeleteView):
    """
        Dynamic registration view.
        Triggers the dynamic registration handler, which creates an LtiTool entry in the database.

        Documentation about the dynamic registration protocol is at https://www.imsglobal.org/spec/lti-dr/v1p0.

        On GET, shows a confirmation message about using the given token to register the tool with the given OpenID configuration.

        On POST, completes the registration and returns a page which does a JavaScript postMessage call to the platform to tell it that registration is complete.
    """

    model = LTIConsumerRegistrationToken
    context_object_name = 'token'
    template_name = 'numbas_lti/lti_13/registration/use_token.html'

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        try:
            self.get_object()
        except Http404 as e:
            return self.show_error(_('The given registration token could not be found. It may have already been used.'))

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)

        registration = DynamicRegistration(self.request)
        context['registration'] = registration
        openid_configuration = context['openid_configuration'] = registration.get_openid_configuration()
        context['platform_name'] = registration.get_platform_name(openid_configuration)

        platform_config = context['platform_config'] = openid_configuration.get('https://purl.imsglobal.org/spec/lti-platform-configuration', {})

        messages_supported = [m.get('type') for m in platform_config.get('messages_supported', [])]
        supports_resource_link = 'LtiResourceLinkRequest' in messages_supported
        supports_deep_link = 'LtiDeepLinkingRequest' in messages_supported

        warnings = context['warnings'] = []

        if not supports_resource_link:
            warnings.append(_('This platform does not support resource links.'))

        if not supports_deep_link:
            warnings.append(_('This platform does not support deep-linking content selection.'))

        return context

    def show_error(self, message):
        return render(self.request,'numbas_lti/launch_errors/registration_error.html',{'error': message})

    def form_valid(self, form):
        token = self.object

        try:
            registration = DynamicRegistration(self.request)

            lti_tool = registration.register()

            token.delete()

        except LtiException as e:
            return self.show_error(e)

        consumer = LTIConsumer.objects.create()
        lti_13_consumer = LTI_13_Consumer.objects.create(consumer=consumer, tool=lti_tool)

        return HttpResponse(registration.complete_html())

class ResourceLaunchView(mixins.LTI_13_Mixin):
    must_have_message_launch = True

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
        message_launch = self.get_message_launch()
        message_launch_data = message_launch.get_launch_data()
        lti_context, resource_link_id = self.get_lti_context()
        lti_13_resource_link = LTI_13_ResourceLink.objects.filter(resource_link_id=resource_link_id, context=lti_context).last()
        if lti_13_resource_link is not None:
            return lti_13_resource_link

        try:
            # See if this is an  LTI link that has been upgraded to LTI 1.3.
            # If so, create a new LTI_13_ResourceLink object.
            lti_11_resource_link = LTI_11_ResourceLink.objects.get(resource_link_id=resource_link_id, context__context_id=lti_context.context_id)
            resource_link_claim = message_launch_data.get('https://purl.imsglobal.org/spec/lti/claim/resource_link')
            resource_link = LTI_13_ResourceLink.objects.create(
                resource = lti_11_resource_link.resource,
                resource_link_id = resource_link_id,
                title = resource_link_claim.get('title'),
                context = lti_context
            )
            return resource_link
        except LTI_11_ResourceLink.DoesNotExist:
            return None

def do_lti_entry(request):
    view = LaunchView()
    view.setup(request)
    return view.do_lti_entry()

class TeacherLaunchView(ResourceLaunchView, View):

    def get(self, request, *args, **kwargs):
        resource_link = self.get_resource_link()

        if resource_link:
            self.record_user_data(resource_link)
            numbas_lti.views.entry.record_launch(request, role='teacher', lti_13_resource_link=resource_link)
            return redirect(self.reverse_with_lti('resource_dashboard', args=(resource_link.resource.pk,)))
        else:
            return render(self.request, 'numbas_lti/launch_errors/no_resource.html', status=404)

class StudentLaunchView(ResourceLaunchView, View):
    def get(self, request, *args, **kwargs):
        resource_link = self.get_resource_link()
    
        self.record_user_data(resource_link)
        numbas_lti.views.entry.record_launch(request, role='student', lti_13_resource_link=resource_link)
        return numbas_lti.views.entry.student_launch(request, resource_link.resource)

class MustBeDeepLinkMixin(mixins.LTI_13_Mixin):
    must_have_message_launch = True

    def check_message_launch(self):
        super().check_message_launch()
        message_launch = self.get_message_launch()

        if not message_launch.is_deep_link_launch():
            raise SuspiciousOperation(_("This action can only be performed as part of a deep-link launch."))

class DeepLinkView(MustBeDeepLinkMixin, TemplateView):
    template_name = "numbas_lti/lti_13/deep_link.html"

    def get(self, *args, **kwargs):
        if not self.get_resources().exists():
            return redirect(self.reverse_with_lti('lti_13:deep_link_create_resource'))

        return super().get(*args, **kwargs)

    def get_resources(self):
        lti_context, _ = self.get_lti_context()
        return Resource.objects.filter(lti_13_links__context=lti_context).distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        message_launch = self.get_message_launch()
        message_launch_data = message_launch.get_launch_data()
        context['message_launch_data'] = message_launch_data

        resource_link_claim = message_launch_data.get('https://purl.imsglobal.org/spec/lti/claim/resource_link')
        context['resource_link_claim'] = resource_link_claim

        lti_context, _ = self.get_lti_context()
        context['lti_context'] = lti_context

        context['resources'] = self.get_resources()

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

        exam.resource = resource
        exam.save()

        message_launch = self.get_message_launch()

        return deep_link_response(self.request, message_launch, resource)
