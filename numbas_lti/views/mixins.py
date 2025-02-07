from django import http
from django.conf import settings
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.http import QueryDict
from django.templatetags.static import static
from django.shortcuts import redirect, render
from django_auth_lti.patch_reverse import reverse
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views import generic
from django.views.decorators.csrf import csrf_exempt
from django_auth_lti.mixins import LTIRoleRestrictionMixin
from django_auth_lti.verification import is_allowed
from functools import wraps
from numbas_lti import lockdown_app, requests_session
from numbas_lti.models import Resource, Exam, LTIContext
from numbas_lti.middleware import get_lti_13_context
import pylti1p3.roles
from pylti1p3.contrib.django import DjangoMessageLaunch, DjangoCacheDataStorage
from pylti1p3.contrib.django.lti1p3_tool_config import DjangoDbToolConf
from pylti1p3.exception import LtiException, LtiMessageValidationException, LtiInvalidNonceException
import urllib.parse

INSTRUCTOR_ROLES = getattr(settings,'LTI_INSTRUCTOR_ROLES', {})
INSTRUCTOR_ROLES.setdefault('lti_11', ['Instructor','Administrator','ContentDeveloper','Manager','TeachingAssistant'])
INSTRUCTOR_ROLES.setdefault('lti_13', [pylti1p3.roles.TeacherRole, pylti1p3.roles.TeachingAssistantRole, pylti1p3.roles.StaffRole, pylti1p3.roles.DesignerRole,])

def reverse_with_lti(request, view_name, args=[], current_app=None, kwargs={}):
    """
        Reverse a view name to a URL, and add in any LTI launch data as a query parameter.
        LTI 1.1 launch data is added automatically by the patched ``reverse`` method. For LTI 1.3, the launch ID is added here.
    """

    url = reverse(view_name, args=args, kwargs=kwargs, current_app=current_app)

    if hasattr(request, 'lti_13_message_launch'):
        message_launch = request.lti_13_message_launch

        query_dict = QueryDict(mutable=True)

        query_dict['lti_13_launch_id'] = message_launch.get_launch_id()

        url += '?' + query_dict.urlencode()
    
    return url

def get_lti_entry_url(request):
    return request.build_absolute_uri(reverse('lti_entry',exclude_resource_link_id=True))

def get_config_url(request):
    return request.build_absolute_uri(reverse('config_xml',exclude_resource_link_id=True))

def request_is_instructor(request):
    if request.user.is_superuser:
        return True

    # LTI 1.3
    if hasattr(request, 'lti_13_message_launch'):
        message_launch = request.lti_13_message_launch
        return message_launch.check_teacher_access() or message_launch.check_teaching_assistant_access() or message_launch.check_staff_access()

    # LTI 1.1
    return bool(is_allowed(request,INSTRUCTOR_ROLES['lti_11'],False))

def request_is_student(request):
    # LTI 1.3
    if hasattr(request, 'lti_13_message_launch'):
        message_launch = request.lti_13_message_launch
        return message_launch.check_student_access()

    # LTI 1.1
    return not request_is_instructor(request)

def static_view(template_name):
    return generic.TemplateView.as_view(template_name=template_name)

class LTI_13_Mixin:
    """
        A view mixin which adds can get LTI 1.3 message launch data.
        The message launch data is loaded from cache by the middleware, or POST parameters if the request is part of a launch.
    """

    tool_conf_cls = DjangoDbToolConf
    launch_data_storage_cls = DjangoCacheDataStorage

    message_launch_cls = DjangoMessageLaunch

    must_have_message_launch = False    # If True, then an error will be shown if no LTI launch data can be found for this request.

    launch_error_template = 'numbas_lti/launch_errors/not_an_lti_launch.html'

    def __init__(self, *args, **kwargs):
        self.tool_conf = self.tool_conf_cls()
        self.launch_data_storage = self.launch_data_storage_cls()

        return super().__init__(*args, **kwargs)

    def dispatch(self, request, *args, **kwargs):
        try:
            self.check_message_launch()
        except LtiMessageValidationException as exception:
            hint = None
            if isinstance(exception, LtiInvalidNonceException):
                hint = '''This might be due to a misconfiguration of the cache. The administrator should check the server's <code>CACHES</code> setting.'''
            return render(self.request, 'numbas_lti/launch_errors/message_validation_error.html', {'exception': exception, 'hint': hint})
        except Exception as exception:
            return render(self.request, self.launch_error_template, {'exception': exception, 'debug':settings.DEBUG, 'post_data': sorted(request.POST.items(),key=lambda x:x[0])})

        return super().dispatch(request, *args, **kwargs)

    def check_message_launch(self):
        if not self.must_have_message_launch:
            return

        message_launch = self.get_message_launch()

        if not message_launch:
            raise SuspiciousOperation(_("This URL is supposed to be used to launch an LTI activity, but no LTI data was found."))

    def get_message_launch(self):
        if not hasattr(self.request, 'lti_13_message_launch'):
            message_launch = self.message_launch_cls(self.request, self.tool_conf, launch_data_storage = self.launch_data_storage, requests_session=requests_session.get_session())
            message_launch.validate()
            self.request.lti_13_message_launch = message_launch

        return self.request.lti_13_message_launch

    def get_lti_context(self):
        if getattr(self, 'context', None) is None:
            self.lti_context = get_lti_13_context(self.get_message_launch())
        return self.lti_context

    def get_custom_param(self, param_name, default=None):
        message_launch_data = self.get_message_launch().get_launch_data()

        return message_launch_data\
            .get('https://purl.imsglobal.org/spec/lti/claim/custom', {})\
            .get(param_name, default)

    def reverse_with_lti(self, *args, **kwargs):
        return reverse_with_lti(self.request, *args, **kwargs)

class LTIRoleOrSuperuserMixin(LTI_13_Mixin, LTIRoleRestrictionMixin):
    raise_exception = False

    allowed_roles = None

    @property
    def redirect_url(self):
        return reverse('not_authorized')+'?originalurl='+urllib.parse.quote(self.request.path+'?'+self.request.META.get('QUERY_STRING',''))

    def check_allowed(self, request):
        if request.user.is_superuser or self.allowed_roles is None:
            return True
        else:
            try:
                message_launch = self.get_message_launch()
                jwt_body = message_launch._get_jwt_body()
                for role in self.allowed_roles['lti_13']:
                    if role(jwt_body).check():
                        return True
            except (AttributeError, LtiException):
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
            def check_allowed():
                try:
                    message_launch = request.lti_13_message_launch
                    jwt_body = message_launch._get_jwt_body()
                    for role in allowed_roles['lti_13']:
                        if role(jwt_body).check():
                            return True
                except (AttributeError, LtiException):
                    if is_allowed(request, allowed_roles['lti_11'], raise_exception=False):
                        return True

            if request.user.is_superuser or check_allowed():
                return view_func(request, *args, **kwargs)
            
            return redirect(redirect_url+'?originalurl='+urllib.parse.quote(request.path+'?'+request.META.get('QUERY_STRING','')))
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

        return super(ResourceManagementViewMixin,self).dispatch(*args,**kwargs)

class MustHaveExamMixin(object):
    def dispatch(self,*args,**kwargs):
        resource = self.get_resource()
        if resource.exam is None:
            return redirect(self.reverse_with_lti('create_exam',args=(resource.pk,)))

        return super(MustHaveExamMixin,self).dispatch(*args,**kwargs)

class HelpLinkMixin(object):
    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args,**kwargs)
        context['page_helplink'] = self.helplink
        return context

def needs_lockdown_app(request):
    if not hasattr(request,'resource'):
        return False

    if request.user.is_superuser:
        return False

    if request_is_instructor(request):
        return False

    require_lockdown_app, _, _ = request.resource.require_lockdown_app_for_user(request.user)
    return require_lockdown_app != ''

class RequireLockdownAppMixin(object):
    def dispatch(self,*args,**kwargs):
        if needs_lockdown_app(self.request):
            controller = lockdown_app.lockdown_app_controller(self.request)
            if not controller.is_lockdown_app():
                return http.HttpResponseForbidden(_('This resource can only be accessed through {app_name}.').format(app_name=controller.app_name_display))

        return super().dispatch(*args,**kwargs)

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)

        context['require_lockdown_app'] = needs_lockdown_app(self.request)

        return context
