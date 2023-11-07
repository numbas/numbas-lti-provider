import logging

from .models import Resource, LTIContext, LTIConsumer, LTI_11_ResourceLink

logger = logging.getLogger(__name__)

class NumbasLTIResourceMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self,request):
        resource_link_id = request.LTI.get('resource_link_id')
        #logger.debug('Numbas LTI middleware processing request {}'.format(request))
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

        response = self.get_response(request)

        return response
