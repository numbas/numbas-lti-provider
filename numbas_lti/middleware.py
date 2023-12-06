import logging
from pylti1p3.contrib.django import DjangoMessageLaunch, DjangoCacheDataStorage
from pylti1p3.contrib.django.lti1p3_tool_config import DjangoDbToolConf

from .models import Resource, LTIContext, LTIConsumer, LTI_11_ResourceLink, LtiTool, LTI_13_ResourceLink

logger = logging.getLogger(__name__)

class NumbasLTIResourceMiddleware(object):
    tool_conf = DjangoDbToolConf()
    launch_data_storage = DjangoCacheDataStorage()
    launch_id_param = 'lti_13_launch_id'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self,request):
        self.get_lti_11_resource_link(request)

        self.get_lti_13_resource_link(request)

        response = self.get_response(request)
        return response

    def get_lti_11_resource_link(self, request):
        if not hasattr(request, 'LTI'):
            return

        resource_link_id = request.LTI.get('resource_link_id')
        if resource_link_id is not None and tool_consumer_instance_guid is not None:
            context_id = request.LTI.get('context_id')
            context_id = context_id if context_id is not None else resource_link_id
            name = request.LTI.get('context_title')
            name = name if name is not None else context_id
            label = request.LTI.get('context_label')
            label = label if label is not None else name

            consumer_key = request.LTI.get('oauth_consumer_key')
            consumer = LTIConsumer.objects.get(lti_11__key=consumer_key)

            context, _ = LTIContext.objects.get_or_create(
                context_id=context_id,
                consumer=consumer,
                defaults = {
                    'name': name,
                    'label': label,
                }
            )
            if (name,label) != (context.name,context.label):
                context.name = name
                context.label = label
                context.save(update_fields=('name', 'label'))

            title = request.LTI.get('resource_link_title')
            if title is None:
                title = ''
            description = request.LTI.get('resource_link_description')
            if description is None:
                description = ''

            try:
                resource_link = LTI_11_ResourceLink.objects.filter(context=context, resource_link_id=resource_link_id).last()
                resource = resource_link.resource
            except LTI_11_ResourceLink.DoesNotExist:
                resource = Resource.objects.create(title=title, description=description)
                resource_link = LTI_11_ResourceLink.objects.create(resource=resource, context=context, resource_link_id=resource_link_id)
            finally:
                if (title,description) != (resource.title,resource.description):
                    resource.title = title
                    resource.description = description
                    resource.save(update_fields=('title', 'description'))
                request.resource = resource

    def get_lti_13_resource_link(self, request):
        launch_id = request.POST.get(self.launch_id_param, request.GET.get(self.launch_id_param, getattr(request, 'kwargs', {}).get(self.launch_id_param)))
        if not launch_id:
            return

        message_launch = DjangoMessageLaunch.from_cache(launch_id, request, self.tool_conf, launch_data_storage=self.launch_data_storage)
        request.lti_13_message_launch = message_launch

        try:
            message_launch_data = message_launch.get_launch_data()
            resource_link_claim = message_launch_data.get('https://purl.imsglobal.org/spec/lti/claim/resource_link')
            resource_link_id = resource_link_claim.get('id')

            iss = message_launch.get_iss()
            client_id = message_launch.get_client_id()
            lti_tool = message_launch.get_tool_conf().get_lti_tool(iss, client_id)

            consumer = lti_tool.numbas.consumer

            context_claim = message_launch_data.get('https://purl.imsglobal.org/spec/lti/claim/context',{})

            context_id = str(context_claim.get('id',''))
            context_title = context_claim.get('title','')
            context_label = context_claim.get('label','')

            lti_context, _ = LTIContext.objects.get_or_create(
                context_id=context_id,
                consumer=consumer,
                defaults = {
                    'name': context_title,
                    'label': context_label,
                }
            )

            request.lti_13_resource_link = LTI_13_ResourceLink.objects.filter(resource_link_id=resource_link_id, context=lti_context).last()
            request.resource = request.lti_13_resource_link.resource
        except (LTI_13_ResourceLink.DoesNotExist, LtiTool.DoesNotExist):
            pass
