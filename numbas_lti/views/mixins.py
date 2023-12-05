from django import http
from django.conf import settings
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.http import QueryDict
from django.templatetags.static import static
from django.shortcuts import redirect
from django_auth_lti.patch_reverse import reverse
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views import generic
from django.views.decorators.csrf import csrf_exempt
from django_auth_lti.mixins import LTIRoleRestrictionMixin
from django_auth_lti.verification import is_allowed
from functools import wraps
from numbas_lti import lockdown_app
from numbas_lti.models import Resource, Exam, LTIContext
import pylti1p3.roles
from pylti1p3.contrib.django import DjangoMessageLaunch, DjangoCacheDataStorage
from pylti1p3.contrib.django.lti1p3_tool_config import DjangoDbToolConf
import urllib.parse

INSTRUCTOR_ROLES = getattr(settings,'LTI_INSTRUCTOR_ROLES', {})
INSTRUCTOR_ROLES.setdefault('lti_11', ['Instructor','Administrator','ContentDeveloper','Manager','TeachingAssistant'])
INSTRUCTOR_ROLES.setdefault('lti_13', [pylti1p3.roles.TeacherRole, pylti1p3.roles.TeachingAssistantRole, pylti1p3.roles.StaffRole, pylti1p3.roles.DesignerRole,])

def get_lti_entry_url(request):
    return request.build_absolute_uri(reverse('lti_entry',exclude_resource_link_id=True))

def get_config_url(request):
    return request.build_absolute_uri(reverse('config_xml',exclude_resource_link_id=True))

def request_is_instructor(request):
    if request.user.is_superuser:
        return True
    return bool(is_allowed(request,INSTRUCTOR_ROLES['lti_11'],False))

def static_view(template_name):
    return generic.TemplateView.as_view(template_name=template_name)


class LTI_13_Mixin:
    """
        A view mixin which adds can get LTI 1.3 message launch data.
        The message launch data is loaded from POST parameters or the django cache.

        For views which need access to the launch data after the launch/login flow, use CachedLTI_13_Mixin.
    """

    tool_conf = DjangoDbToolConf()
    launch_data_storage = DjangoCacheDataStorage()

    message_launch_cls = DjangoMessageLaunch

    """
        Should this view try to get the message launch at the start of the dispatch method?
        Return False if this view should sometimes work without an LTI launch.
    """
    get_message_launch_on_dispatch = True

    def get_lti_data(self):
        self.message_launch = self.get_message_launch()
        self.lti_tool = self.get_lti_tool()
        self.lti_context = self.get_lti_context()

    def get_message_launch(self):
        message_launch = self.message_launch_cls(self.request, self.tool_conf, launch_data_storage = self.launch_data_storage)
        return message_launch

    def get_lti_tool(self):
        iss = self.message_launch.get_iss()
        client_id = self.message_launch.get_client_id()
        tool = self.message_launch.get_tool_conf().get_lti_tool(iss, client_id)
        return tool

    def get_lti_context(self):
        lti_tool = self.get_lti_tool()

        consumer = lti_tool.numbas.consumer

        message_launch_data = self.message_launch.get_launch_data()

        context_claim = message_launch_data.get('https://purl.imsglobal.org/spec/lti/claim/context',{})

        context_id = str(context_claim.get('id',''))
        context_title = context_claim.get('title','')
        context_label = context_claim.get('label','')

        context, _ = LTIContext.objects.get_or_create(
            context_id=context_id,
            consumer=consumer,
            defaults = {
                'name': context_title,
                'label': context_label,
            }
        )

        self.context = context

        return context

    def get_custom_param(self, param_name):
        message_launch_data = self.message_launch.get_launch_data()

        return message_launch_data.get('https://purl.imsglobal.org/spec/lti/claim/custom', {})\
            .get(param_name)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if hasattr(self, 'message_launch'):
            context['message_launch'] = self.message_launch

        return context

    def reverse_with_lti(self, view_name, args, current_app=None, kwargs={}):
        query_dict = QueryDict(mutable=True)

        message_launch = self.get_message_launch()
        query_dict['lti_13_launch_id'] = message_launch.get_launch_id()

        url = reverse(view_name, args=args, kwargs=kwargs, current_app=current_app)

        query = query_dict.urlencode()
        if query:
            url += '?' + query
        
        return url

class CachedLTI_13_Mixin(LTI_13_Mixin):
    """
        A view mixin which adds a message_launch object to the view object.
        The message launch data is loaded from cache storage.

        The ID of the launch must be provided either as a POST parameter or in the query part of the URL under the key defined by the launch_id_param property.
    """

    launch_id_param = 'lti_13_launch_id'

    def get_launch_id(self):
        post_param = self.request.POST.get(self.launch_id_param, self.request.GET.get(self.launch_id_param))
        if post_param:
            return post_param
        
        return self.kwargs.get(self.launch_id_param)

    def get_message_launch(self):
        launch_id = self.get_launch_id()
        if launch_id is None:
            raise SuspiciousOperation

        message_launch = self.message_launch_cls.from_cache(launch_id, self.request, self.tool_conf, launch_data_storage = self.launch_data_storage)

        return message_launch

    def get_context_data(self, **kwargs):
        self.get_lti_data()
        return  super().get_context_data(**kwargs)


class LTI_13_Only_Mixin:
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        if self.get_message_launch_on_dispatch:
            self.get_lti_data()
        return super().dispatch(request, *args, **kwargs)


class LTIRoleOrSuperuserMixin(CachedLTI_13_Mixin, LTIRoleRestrictionMixin):
    raise_exception = False

    @property
    def redirect_url(self):
        return reverse('not_authorized')+'?originalurl='+urllib.parse.quote(self.request.path+'?'+self.request.META.get('QUERY_STRING',''))

    def check_allowed(self, request):
        if request.user.is_superuser:
            return True
        else:
            try:
                launch_id = self.get_launch_id()
                message_launch = self.get_message_launch()
                jwt_body = message_launch._get_jwt_body()
                for role in self.allowed_roles['lti_13']:
                    if role(jwt_body).check():
                        return True
            except AttributeError:
                if is_allowed(request, self.allowed_roles['lti_11'], raise_exception=False):
                    return True

            if self.raise_exception:
                raise PermissionDenied
            else:
                return False

class MustBeInstructorMixin(LTIRoleOrSuperuserMixin):
    allowed_roles = INSTRUCTOR_ROLES

def lti_role_or_superuser_required(allowed_roles, redirect_url=reverse_lazy('not_authorized'), raise_exception=False):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if request.user.is_superuser or is_allowed(request, allowed_roles, raise_exception):
                return view_func(request, *args, **kwargs)
            
            return redirect(redirect_url+'?originalurl='+urllib.parse.quote(self.request.path+'?'+self.request.META.get('QUERY_STRING','')))
        return _wrapped_view
    return decorator

class ManagementViewMixin(object):
    def get_context_data(self,*args,**kwargs):
        context = super(ManagementViewMixin,self).get_context_data(*args,**kwargs)
        context.update({
            'management_tab': self.management_tab
        })
        return context

class ResourceManagementViewMixin(ManagementViewMixin):
    context_object_name = 'resource'
    resource_pk_url_kwarg = 'pk'

    def get_resource(self):
        if self.model == Resource:
            return self.get_object()
        else:
            pk = self.kwargs.get(self.resource_pk_url_kwarg)
            return Resource.objects.get(pk=pk)

    def get_context_data(self,*args,**kwargs):
        context = super().get_context_data(*args,**kwargs)
        context['resource'] = self.get_resource()
        return context

    def dispatch(self,*args,**kwargs):
        self.resource = self.get_resource()
        if not hasattr(self.request,'resource') or self.request.resource is None:
            self.request.resource = self.resource

        return super(ResourceManagementViewMixin,self).dispatch(*args,**kwargs)

class MustHaveExamMixin(object):
    def dispatch(self,*args,**kwargs):
        resource = self.get_resource()
        if resource.exam is None:
            return redirect(reverse('create_exam',args=(resource.pk,)))

        return super(MustHaveExamMixin,self).dispatch(*args,**kwargs)

class HelpLinkMixin(object):
    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args,**kwargs)
        context['page_helplink'] = self.helplink
        return context

def needs_lockdown_app(request):
    if not hasattr(request,'resource'):
        return False
    if request_is_instructor(request):
        return False

    return request.resource.require_lockdown_app != ''

class RequireLockdownAppMixin(object):
    def dispatch(self,*args,**kwargs):
        if needs_lockdown_app(self.request) and not lockdown_app.is_lockdown_app(self.request):
            return http.HttpResponseForbidden(_('This resource can only be accessed through the Numbas lockdown app'))
        else:
            return super().dispatch(*args,**kwargs)
