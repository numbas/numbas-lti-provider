from . import version
from django.conf import settings
import requests

def get_session():
    REQUESTS_USER_AGENT = getattr(settings, 'REQUESTS_USER_AGENT', 'Numbas LTI provider')
    session = requests.Session()
    session.headers['User-Agent'] = f'{REQUESTS_USER_AGENT} {version}'
    return session
