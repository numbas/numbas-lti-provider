from .models import Resource

class NumbasLTIResourceMiddleware(object):
    def process_request(self,request):
        resource_link_id = request.LTI.get('resource_link_id')
        tool_consumer_instance_guid = request.LTI.get('tool_consumer_instance_guid')
        if resource_link_id is not None and tool_consumer_instance_guid is not None:
            try:
                request.resource = Resource.objects.get(resource_link_id=resource_link_id, tool_consumer_instance_guid=tool_consumer_instance_guid)
            except Resource.DoesNotExist:
                request.resource = Resource.objects.create(resource_link_id=resource_link_id, tool_consumer_instance_guid=tool_consumer_instance_guid)

