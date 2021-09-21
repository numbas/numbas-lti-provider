from django.urls import re_path
from channels.routing import route, route_class
from numbas_lti import consumers

channel_routing = [

    route_class(consumers.AttemptScormListingConsumer, path=r'^/websocket/attempt/(?P<pk>\d+)/scorm_listing$'),

    route("attempt.email_receipt",consumers.email_receipt),
    route("report.all_scores",consumers.report_scores),
    route("report.attempt",consumers.report_score),
    route("editorlink.update_cache",consumers.update_editorlink),
]
