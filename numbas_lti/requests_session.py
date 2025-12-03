from . import version
from django.conf import settings
import requests

class Session(requests.Session):
    def send(self, request, **kwargs):
        if kwargs.get('timeout') is None:
            kwargs['timeout'] = (5,30)
        return super().send(request, **kwargs)

def get_session():
    REQUESTS_USER_AGENT = getattr(settings, 'REQUESTS_USER_AGENT', 'Numbas LTI provider')
    session = Session()
    session.headers['User-Agent'] = f'{REQUESTS_USER_AGENT} {version}'
    return session
