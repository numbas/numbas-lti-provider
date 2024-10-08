import binascii
from Crypto import Random
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from django_auth_lti.patch_reverse import reverse
from django.conf import settings
from django.core import signing
from django.utils.translation import gettext_lazy as _
import gzip
import hashlib
import hmac
import json
from pylti1p3.contrib.django import DjangoCacheDataStorage
from pylti1p3.contrib.django.cookie import DjangoCookieService
from pylti1p3.contrib.django.request import DjangoRequest
import os
import re
import urllib.parse
from .util import add_query_param


def make_key(password):
    key = hashlib.scrypt(password.encode('utf-8'),salt=settings.LOCKDOWN_APP['salt'].encode('utf-8'),n=16384,r=8,p=1)
    return key[:24]

def encrypt(password, message):
    msglist = []
    key = make_key(password)
    iv = Random.new().read(AES.block_size)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    encrypted = cipher.encrypt(pad(message.encode('utf-8'), AES.block_size))
    return iv, encrypted

def get_ltip3_session_id(request):
    lti1p3_request = DjangoRequest(request)
    launch_data_storage = DjangoCacheDataStorage()
    launch_data_storage.set_request(lti1p3_request)
    cookie_service = DjangoCookieService(lti1p3_request)
    return cookie_service.get_cookie(launch_data_storage.get_session_cookie_name())

def make_link(request):
    params = request.GET.copy()
    params.update({
        'session_key': request.session.session_key,
        'lti1p3-session-id': get_ltip3_session_id(request),
    })


    launch_url = add_query_param(
        request.build_absolute_uri(reverse('lockdown_launch')),
        params
    )

    token = token_for_request(request)

    link_settings = {
        'url': launch_url,
        'token': token,
    }

    password = request.resource.get_lockdown_app_password(user=request.user)

    iv, encrypted = encrypt(password, json.dumps(link_settings))
    url = f'numbas://{request.get_host()}/'+binascii.hexlify(iv+encrypted).decode('ascii')
    return url

def token_for_request(request):
    return signing.dumps({
        'resource': request.resource.pk,
        'user': request.user.pk,
    })

def validate_token(request, token):
    d = signing.loads(token)
    return isinstance(d,dict) and d.get('resource') == request.resource.pk and d.get('user') == request.user.pk

def is_lockdown_app(request):
    required, lockdown_app_password, seb_settings = request.resource.require_lockdown_app_for_user(request.user)

    checker = {
        'numbas': is_numbas_lockdown_app,
        'seb': is_seb,
    }

    try:
        fn = checker[required]
    except KeyError:
        return False

    return fn(request, lockdown_app_password=lockdown_app_password, seb_settings=seb_settings)

def is_numbas_lockdown_app(request, **kwargs):
    header = request.META.get('HTTP_AUTHORIZATION')
    if header is None:
        return False

    m = re.match(r'^Basic (?P<token>.*)$',header)
    if not m:
        return False
    
    token = m.group('token')

    try:
        validate_token(request, token)
    except signing.BadSignature:
        return False

    return True

def make_seb_link(request):
    params = request.GET.copy()
    params.update({
        'session_key': request.session.session_key,
        'lti1p3-session-id': get_ltip3_session_id(request),
    })

    query = '&'.join(f'{k}={urllib.parse.quote(v)}' for k,v in params.items() if v is not None)

    _, _, seb_settings = request.resource.require_lockdown_app_for_user(request.user)
    settings_url = seb_settings.settings_file.url

    scheme = 'sebs' if request.is_secure() else 'seb'
    url = urllib.parse.urlunparse((scheme, request.get_host(), settings_url, '', '', ''))+'??'+query
    return url

def is_seb(request, seb_settings=None, **kwargs):
    """
        Check that the request has come from SEB.
        The Mac and iOS apps don't send this header any more, so this only works for Windows SEB.

        There's a description of how this is supposed to work at https://safeexambrowser.org/developer/seb-config-key.html
    """

    if seb_settings is None:
        return False

    header_hash = request.headers.get('X-Safeexambrowser-Configkeyhash')
    uri = request.build_absolute_uri()
    key = seb_settings.config_key_hash

    expected_hash = hashlib.sha256((uri + key).encode('utf-8')).hexdigest()

    return header_hash == expected_hash

SaltBitSize = 64
KeyBitSize = 256
BlockBitSize = 128
Iterations = 10000
PASSWORD_MODE = 'pswd'
RNCRYPTOR_HEADER = b'\x02\x01'

def encrypt_seb_settings(xml: str, password: str):
    cleanedxml = (xml
        .replace('<array />', '<array></array>')
        .replace('<dict />', '<dict></dict>')
        .replace('<data />', '<data></data>')
    )
    data = cleanedxml.encode('utf-8')

    compressed = gzip.compress(data)

    prefixString = PASSWORD_MODE

    cryptSalt = os.urandom(SaltBitSize//8)
    cryptKey = hashlib.pbkdf2_hmac('sha1', password.encode('utf-8'), cryptSalt, Iterations, KeyBitSize//8)

    authSalt = os.urandom(SaltBitSize//8)
    authKey = hashlib.pbkdf2_hmac('sha1', password.encode('utf-8'), authSalt, Iterations, KeyBitSize//8)

    aes = AES.new(cryptKey, AES.MODE_CBC)
    iv = aes.iv

    ciphertext = aes.encrypt(pad(compressed, BlockBitSize//8))

    body = RNCRYPTOR_HEADER + cryptSalt + authSalt + iv + ciphertext

    tag = hmac.new(authKey, body, digestmod='sha256').digest()

    out_data = prefixString.encode('utf-8') + body + tag

    compressed_encrypted = gzip.compress(out_data)

    return compressed_encrypted
