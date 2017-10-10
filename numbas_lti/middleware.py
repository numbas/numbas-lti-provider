from .models import Resource, LTIContext, LTIConsumer

class NumbasLTIResourceMiddleware(object):
    def process_request(self,request):
        resource_link_id = request.LTI.get('resource_link_id')
        tool_consumer_instance_guid = request.LTI.get('tool_consumer_instance_guid')
        if resource_link_id is not None and tool_consumer_instance_guid is not None:
            context_id = request.LTI.get('context_id')
            name = request.LTI.get('context_title')
            label = request.LTI.get('context_label')
            instance_guid = request.LTI.get('tool_consumer_instance_guid')
            try:
                context = LTIContext.objects.get(context_id=context_id,instance_guid=instance_guid)
                if (name,label) != (context.name,context.label):
                    context.name = name
                    context.label = label
                    context.save()
            except LTIContext.DoesNotExist:
                context = LTIContext.objects.create(
                        consumer = LTIConsumer.objects.get(key=request.POST.get('oauth_consumer_key')),
                        context_id=context_id, 
                        name=request.LTI.get('context_title'), 
                        label=request.LTI.get('context_label'), 
                        instance_guid=request.LTI.get('tool_consumer_instance_guid')
                    )
            title = request.LTI.get('resource_link_title')
            description = request.LTI.get('resource_link_description')
            try:
                resource = Resource.objects.get(resource_link_id=resource_link_id)
                if (title,description,context) != (resource.title,resource.description,resource.context):
                    resource.title = title
                    resource.description = description
                    resource.context = context
                    resource.save()
                request.resource = resource
            except Resource.DoesNotExist:
                request.resource = Resource.objects.create(resource_link_id=resource_link_id, context=context, title=title, description=description)
