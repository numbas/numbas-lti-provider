from django.conf import settings
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
from urllib.parse import parse_qs

from django.contrib.auth.models import User
from django.utils.translation import ugettext as _
from django_auth_lti.patch_reverse import reverse

from .groups import group_for_attempt, group_for_resource_stats, group_for_resource
from .models import Attempt, ScormElement, Resource, ReportProcess, EditorLink
from .report_outcome import ReportOutcomeException
from .save_scorm_data import save_scorm_data

@channel_session_user_from_http
def attempt_ws_connect(message,pk):
    message.reply_channel.send({"accept": True})
    attempt = Attempt.objects.get(pk=pk)
    group = group_for_attempt(attempt)
    group.add(message.reply_channel)

    resource = attempt.resource
    resource_group = group_for_resource(attempt.resource)
    resource_group.add(message.reply_channel)

    query = parse_qs(message.content['query_string'].decode('utf-8'))
    uid = query.get('uid',[''])[0]
    mode= query.get('mode',[''])[0]

    if mode!='review':
        group.send({'text': json.dumps({'current_uid': uid, 'availability_dates':resource.availability_json()})})

@channel_session_user_from_http
def attempt_ws_disconnect(message,pk):
    attempt = Attempt.objects.get(pk=pk)
    group_for_attempt(attempt).discard(message.reply_channel)
    group_for_resource(attempt.resource).discard(message.reply_channel)

@channel_session_user
def scorm_set_element(message,pk):
    packet = json.loads(message.content['text'])
    attempt = Attempt.objects.get(pk=pk)
    batches = {packet['id']: packet['data']}
    done, unsaved_elements = save_scorm_data(attempt,batches)
    response = {
        'received': done,
        'completion_status': attempt.completion_status,
        'unsaved_elements': unsaved_elements,
    }
    message.reply_channel.send({'text':json.dumps(response)})

@channel_session_user_from_http
def resource_stats_ws_connect(message,pk):
    user = message.user
    resource = Resource.objects.get(pk=pk)
    message.reply_channel.send({"accept": True})
    group = group_for_resource_stats(resource)
    group.add(message.reply_channel)

@channel_session_user_from_http
def resource_stats_ws_disconnect(message,pk):
    resource = Resource.objects.get(pk=pk)
    group = group_for_resource_stats(resource)
    group.discard(message.reply_channel)

@channel_session_user
def resource_stats_ws_receive(message,pk):
    resource = Resource.objects.get(pk=pk)

def report_scores(message,**kwargs):
    resource = Resource.objects.get(pk=message['pk'])
    resource.report_scores()

def report_score(message,**kwargs):
    attempt = Attempt.objects.get(pk=message['pk'])
    try:
        attempt.report_outcome()
    except ReportOutcomeException:
        pass
    

class AttemptScormListingConsumer(WebsocketConsumer):
    def connection_groups(self,pk,**kwargs):
        attempt = Attempt.objects.get(pk=pk)
        return [attempt.channels_group()]

def update_editorlink(message,**kwargs):
    editorlink = EditorLink.objects.get(pk=message['pk'])

    editorlink.update_cache(bounce=message.get('bounce',False))
    editorlink.save()

def email_receipt(message,**kwargs):
    attempt = Attempt.objects.get(pk=message['pk'])
    if not attempt.sent_receipt:
        attempt.send_completion_receipt()
