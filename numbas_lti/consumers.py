from django.http import HttpResponse
from channels.handler import AsgiHandler
from channels import Group
from channels.sessions import channel_session
from channels.auth import http_session_user, channel_session_user, channel_session_user_from_http
from channels.generic import BaseConsumer
from channels.generic.websockets import WebsocketConsumer
import json
from datetime import datetime
from django.utils import timezone

from django.contrib.auth.models import User
from django.utils.translation import ugettext as _

from .models import Attempt,ScormElement,Resource, ReportProcess,EditorLink
from .report_outcome import report_outcome, ReportOutcomeException

@channel_session_user
def scorm_set_element(message,pk):
    packet = json.loads(message.content['text'])
    attempt = Attempt.objects.get(pk=pk)
    for element in packet['data']:
        ScormElement.objects.create(
            attempt = attempt,
            key = element['key'], 
            value = element['value'],
            time = timezone.make_aware(datetime.fromtimestamp(element['time'])),
            counter = element['counter']
        )
    response = {
        'received': str(packet['id'])
    }
    message.reply_channel.send({'text':json.dumps(response)})

def report_scores(message,**kwargs):
    resource = Resource.objects.get(pk=message['pk'])
    process = ReportProcess.objects.create(resource=resource)

    for user in User.objects.filter(attempts__resource=resource).distinct():
        try:
            request = report_outcome(resource,user)
        except ReportOutcomeException as e:
            process.status = 'error'
            process.response = e.message
            process.save()
            return

    process.status = 'complete'
    process.save()

class AttemptScormListingConsumer(WebsocketConsumer):
    def connection_groups(self,pk,**kwargs):
        attempt = Attempt.objects.get(pk=pk)
        return [attempt.channels_group()]

def update_editorlink(message,**kwargs):
    editorlink = EditorLink.objects.get(pk=message['pk'])

    editorlink.update_cache(bounce=message.get('bounce',False))
    editorlink.save()
