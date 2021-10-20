from django.urls import path, re_path
from numbas_lti import consumers

websocket_urlpatterns = [
    re_path(r'^websocket/attempt/(?P<pk>\d+)/scorm_listing', consumers.AttemptScormListingConsumer.as_asgi()),
    re_path(r'^websocket/attempt/(?P<pk>\d+)/scorm_api', consumers.RunAttemptConsumer.as_asgi()),
    re_path(r'^websocket/resource/(?P<pk>\d+)/stats', consumers.ResourceStatsConsumer.as_asgi()),
]
