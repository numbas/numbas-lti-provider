from channels.routing import route, route_class
from numbas_lti import consumers

channel_routing = [
    route("websocket.connect",consumers.attempt_ws_connect, path=r'^/websocket/attempt/(?P<pk>\d+)/scorm_api$'),
    route("websocket.disconnect",consumers.attempt_ws_disconnect, path=r'^/websocket/attempt/(?P<pk>\d+)/scorm_api$'),
    route("websocket.receive",consumers.scorm_set_element, path=r'^/websocket/attempt/(?P<pk>\d+)/scorm_api$'),

    route("websocket.connect",consumers.resource_stats_ws_connect, path=r'^/resource/(?P<pk>\d+)/stats/websocket$'),
    route("websocket.receive",consumers.resource_stats_ws_receive, path=r'^/resource/(?P<pk>\d+)/stats/websocket$'),
    route("websocket.disconnect",consumers.resource_stats_ws_disconnect, path=r'^/resource/(?P<pk>\d+)/stats/websocket$'),

    route_class(consumers.AttemptScormListingConsumer, path=r'^/websocket/attempt/(?P<pk>\d+)/scorm_listing$'),
    route("report.all_scores",consumers.report_scores),
    route("editorlink.update_cache",consumers.update_editorlink),
]
