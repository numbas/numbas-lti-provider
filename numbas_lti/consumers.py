from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer
from datetime import datetime
from django_auth_lti.patch_reverse import reverse
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.translation import gettext as _
import json
from urllib.parse import parse_qs


from .groups import group_for_attempt, group_for_resource_stats, group_for_resource
from .models import Attempt, ScormElement, Resource, ReportProcess, EditorLink
from .report_outcome import ReportOutcomeException
from .save_scorm_data import save_scorm_data

class ModelWebsocketConsumer(WebsocketConsumer):
    model = None
    pk_kwarg = 'pk'

    def get_object(self):
        pk = self.scope['url_route']['kwargs'][self.pk_kwarg]
        return self.model.objects.get(pk=pk)

class AttemptConsumer(ModelWebsocketConsumer):
    model = Attempt

    def connect(self):
        self.accept()
        attempt = self.attempt = self.get_object()
        self.attempt_group = group_for_attempt(attempt)
        async_to_sync(self.channel_layer.group_add)(self.attempt_group,self.channel_name)

        self.resource_group = group_for_resource(self.attempt.resource)
        async_to_sync(self.channel_layer.group_add)(self.resource_group,self.channel_name)

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)(self.attempt_group, self.channel_name)
        async_to_sync(self.channel_layer.group_discard)(self.resource_group, self.channel_name)

    def receive(self, text_data):
        packet = json.loads(text_data)
        if packet.get('type') != 'scorm.elements':
            return
        batches = {packet['id']: packet['data']}
        attempt = self.get_object()
        done, unsaved_elements = save_scorm_data(attempt,batches)
        response = {
            'received': done,
            'completion_status': attempt.completion_status,
            'unsaved_elements': unsaved_elements,
        }
        self.send(text_data=json.dumps(response))

    # Message handlers

    def websocket_connected(self,message):
        pass

    def availability_changed(self,message):
        pass

    def completion_status_changed(self,message):
        pass

    def scorm_new_element(self,message):
        pass

class RunAttemptConsumer(AttemptConsumer):
    def connect(self):
        super().connect()

        query = parse_qs(self.scope['query_string'].decode('utf-8'))
        uid = query.get('uid',[''])[0]
        mode = query.get('mode',[''])[0]

        if mode!='review':
            # You can only have an attempt open in one place at a time:
            # tell all other connected clients that this client has connected, so that they can disable their Numbas interface
            async_to_sync(self.channel_layer.group_send)(self.attempt_group, {'type': 'websocket.connected', 'current_uid': uid, 'availability_dates':self.attempt.resource.availability_json(self.attempt.user)})

    def websocket_connected(self,message):
        self.send(json.dumps(message))

    def availability_changed(self,message):
        attempt = self.get_object()
        data = {
            'type': 'availability.changed',
            'availability_dates': attempt.resource.availability_json(attempt.user),
        }
        self.send(json.dumps(data))

    def completion_status_changed(self,message):
        self.send(json.dumps(message))


class AttemptScormListingConsumer(AttemptConsumer):
    def scorm_new_element(self,message):
        self.send(json.dumps(message))

class ResourceStatsConsumer(ModelWebsocketConsumer):
    model = Resource

    def connect(self):
        resource = self.get_object()
        self.accept()
        group = group_for_resource_stats(resource)
        async_to_sync(self.channel_layer.group_add)(group, self.channel_name)

    def disconnect(self):
        resource = self.get_object()
        group = group_for_resource_stats(resource)
        async_to_sync(self.channel_layer.group_discard)(group, self.channel_name)
