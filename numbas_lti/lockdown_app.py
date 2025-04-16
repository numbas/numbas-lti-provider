import binascii
from Crypto import Random
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from django_auth_lti.patch_reverse import reverse
from django.conf import settings
from django.core import signing
from django.shortcuts import render
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
    cookie_name = launch_data_storage.get_session_cookie_name() or ''
    return cookie_service.get_cookie(cookie_name)

def token_for_request(request):
    return signing.dumps({
        'resource': request.resource.pk,
        'user': request.user.pk,
    })

def validate_token(request, token):
    d = signing.loads(token)
    return isinstance(d,dict) and d.get('resource') == request.resource.pk and d.get('user') == request.user.pk

class OldVersionException(Exception):
    def __init__(self, version, min_version):
        self.version = version
        self.min_version = min_version

def parse_version(version_string: str):
    try:
        return [int(x) for x in version_string.split('.')]
    except ValueError:
        raise ValueError(f"{version_string} is not a valid version number.")

def compare_versions(a: str, b: str) -> int:
    a = parse_version(a)
    b = parse_version(b)
    return 1 if a > b else -1 if a < b else 0

class LockdownApp:
    app_name = ''
    app_name_display = ''

    def __init__(self, request):
        self.request = request

    def is_lockdown_app(self) -> bool:
        raise NotImplementedError

    def get_app_version(self):
        """ Return (version: str, platform: str)
        """
        raise NotImplementedError

    def get_install_url(self) -> str:
        raise NotImplementedError

    def show_lockdown_link(self):
        """
            Show the link to open the lockdown app.
        """

        raise NotImplementedError


    def check_version(self):
        """ 
            Raises an OldVersionException if the user's version of the app is older than the minimum specified in settings.LOCKDOWN_APP['minimum_version'][this.app_name][platform]
        """
        version, platform = self.get_app_version()

        min_version = settings.LOCKDOWN_APP.get('minimum_version',{}).get(self.app_name,{}).get(platform)
        if min_version is not None:
            if compare_versions(version, min_version) < 0:
                raise OldVersionException(version, min_version)

    def old_version_response(self, err: OldVersionException):
        return render(
            self.request,
            'numbas_lti/lockdown_launch/must_upgrade_app.html',
            {
                'app_name': self.app_name_display,
                'version': err.version,
                'min_version': err.min_version,
                'install_url': self.get_install_url(),
                'client_version': err.version,
            }
        )

    def show_lockdown_link(self):
        launch_url = self.make_launch_url()
        password = self.request.resource.get_lockdown_app_password(user=self.request.user)
        return render(
            self.request,
            'numbas_lti/lockdown_launch/app_link.html',
            {
                'launch_url': launch_url,
                'install_url': settings.LOCKDOWN_APP.get('seb_install_url'),
                'password': password,
                'app_name': self.app_name_display,
            }
        )


class NoLockdownApp(LockdownApp):
    def is_lockdown_app(self):
        return True

    def check_version(self):
        pass


class NumbasLockdownApp(LockdownApp):
    app_name = 'numbas'
    app_name_display = _('Numbas lockdown app')

    def get_install_url(self):
        return settings.LOCKDOWN_APP.get('install_url')

    def is_lockdown_app(self):
        _, lockdown_app_password, _ = self.request.resource.require_lockdown_app_for_user(self.request.user)

        header = self.request.META.get('HTTP_AUTHORIZATION')
        if header is None:
            return False

        m = re.match(r'^Basic (?P<token>.*)$',header)
        if not m:
            return False
        
        token = m.group('token')

        try:
            validate_token(self.request, token)
        except signing.BadSignature:
            return False

        return True

    def get_app_version(self):
        user_agent = self.request.META['HTTP_USER_AGENT']
        info = dict(re.findall(r'\((?P<key>.*?): (?P<value>.*?)\)', user_agent))
        version = info.get('Version')
        platform = info.get('Platform')

        return (version, platform)

    def make_launch_url(self):
        params = self.request.GET.copy()
        params.update({
            'session_key': self.request.session.session_key,
            'lti1p3-session-id': get_ltip3_session_id(self.request),
        })


        launch_url = add_query_param(
            self.request.build_absolute_uri(reverse('lockdown_launch')),
            params
        )

        token = token_for_request(self.request)

        link_settings = {
            'url': launch_url,
            'token': token,
        }

        password = self.request.resource.get_lockdown_app_password(user=self.request.user)

        iv, encrypted = encrypt(password, json.dumps(link_settings))
        url = f'numbas://{self.request.get_host()}/'+binascii.hexlify(iv+encrypted).decode('ascii')
        return url


class SEBApp(LockdownApp):
    app_name = 'seb'
    app_name_display = 'Safe Exam Browser'
    launch_link_template = 'numbas_lti/lockdown_launch/seb_link.html'

    def is_lockdown_app(self):
        """
            Check that the request has come from SEB.
            The Mac and iOS apps don't send this header any more, so this only works for Windows SEB.

            There's a description of how this is supposed to work at https://safeexambrowser.org/developer/seb-config-key.html
        """

        _, _, seb_settings = self.request.resource.require_lockdown_app_for_user(self.request.user)

        if seb_settings is None:
            return False

        header_hash = self.request.headers.get('X-Safeexambrowser-Configkeyhash')
        uri = self.request.build_absolute_uri()
        key = seb_settings.config_key_hash

        expected_hash = hashlib.sha256((uri + key).encode('utf-8')).hexdigest()

        return header_hash == expected_hash

    def make_launch_url(self):
        params = self.request.GET.copy()
        params.update({
            'session_key': self.request.session.session_key,
            'lti1p3-session-id': get_ltip3_session_id(self.request),
        })

        query = '&'.join(f'{k}={urllib.parse.quote(v)}' for k,v in params.items() if v is not None)

        _, _, seb_settings = self.request.resource.require_lockdown_app_for_user(self.request.user)
        settings_url = seb_settings.settings_file.url

        scheme = 'sebs' if self.request.is_secure() else 'seb'
        url = urllib.parse.urlunparse((scheme, self.request.get_host(), settings_url, '', '', ''))+'??'+query
        return url


def lockdown_app_controller(request):
    """ 
        Get the appropriate subclass of LockdownApp for the resource associated with the request.
    """
    required, _, _ = request.resource.require_lockdown_app_for_user(request.user)

    controllers = {
        'numbas': NumbasLockdownApp,
        'seb': SEBApp,
    }

    controller_cls = controllers.get(required, NoLockdownApp)

    return controller_cls(request)


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
