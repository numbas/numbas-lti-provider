from django.http import HttpResponse
from channels.handler import AsgiHandler
from channels import Group
from channels.sessions import channel_session,enforce_ordering
from channels.auth import http_session_user, channel_session_user, channel_session_user_from_http
import json

from .models import Attempt,ScormElement

@enforce_ordering(slight=True)
@channel_session_user_from_http
def ws_add(message):
    print("CONNECT",message.user)
    print(message['path'])

@channel_session_user
def ws_message(message):
    print("MESSAGE",message.user)
    Group(message.channel_session['group']).send({
        "text": '[{}] {}'.format(message.user.get_full_name(),message.content['text']),
    })

@channel_session_user
def ws_disconnect(message):
    print("DISCONNECT",message.user)
    Group(message.channel_session['group']).discard(message.reply_channel)


@enforce_ordering(slight=True)
@channel_session_user_from_http
def scorm_connect(message,pk):
    print("CONNECT SCORM",message.user)
    print(message.content['path'])

@channel_session_user
def scorm_set_element(message,pk):
    print("SET")
    print(pk)
    data = json.loads(message.content['text'])
    print(data)
    attempt = Attempt.objects.get(pk=pk)
    ScormElement.objects.create(
        attempt = attempt,
        key = data['key'], 
        value = data['value']
    )
