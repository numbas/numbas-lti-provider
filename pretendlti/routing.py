from channels.routing import route
from numbas_lti import consumers

channel_routing = [
    route("websocket.connect", consumers.ws_add),

    route("websocket.connect",consumers.scorm_connect, path=r'^/scorm_api/$'),
    route("websocket.receive",consumers.scorm_set_element, path=r'^/scorm_api/$'),
]
