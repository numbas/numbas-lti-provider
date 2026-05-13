from . import version
from django.conf import settings
from django.utils.module_loading import import_string
import requests
from requests_cache import CachedSession, RedisCache

class Session(CachedSession):
    def send(self, request, **kwargs):
        if kwargs.get('timeout') is None:
            kwargs['timeout'] = (5,30)
        return super().send(request, **kwargs)

def get_session():
    REQUESTS_USER_AGENT = getattr(settings, 'REQUESTS_USER_AGENT', 'Numbas LTI provider')
    REQUESTS_CACHE = getattr(settings, 'REQUESTS_CACHE', {})
    backend_cls = import_string(REQUESTS_CACHE.get('BACKEND', 'requests_cache.RedisCache'))
    backend = backend_cls(**REQUESTS_CACHE.get('SETTINGS',{}))
    session = Session('numbas_lti_requests', backend=backend)
    session.headers['User-Agent'] = f'{REQUESTS_USER_AGENT} {version}'
    return session
