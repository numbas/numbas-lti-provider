import os

import django
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

from .debug_handler import DebugASGIHandler

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "numbasltiprovider.settings")

django.setup(set_prefix=False)
django_asgi_app = DebugASGIHandler()

import numbas_lti.routing

application = ProtocolTypeRouter({
  "http": django_asgi_app,
  "websocket": AuthMiddlewareStack(
        URLRouter(
            numbas_lti.routing.websocket_urlpatterns
        )
    ),
})
