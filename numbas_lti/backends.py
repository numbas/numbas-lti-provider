from django_auth_lti import backends
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.core.exceptions import PermissionDenied
import logging
from numbas_lti.models import LTIConsumer, LTI_11_Consumer, LTI_11_UserAlias, LTI_13_UserAlias
from oauthlib.oauth1.rfc5849.utils import UNICODE_ASCII_CHARACTER_SET
from pylti1p3.exception import LtiException
from pylti1p3.contrib.django import DjangoMessageLaunch, DjangoCacheDataStorage
from pylti1p3.contrib.django.lti1p3_tool_config import DjangoDbToolConf
import uuid

logger = logging.getLogger(__name__)

def new_lti_user():
    """
        Create a new User object during an LTI launch.
        The username is a UUID; in order to find this user again, a user alias record must be created associating the consumer and its ID for the user with this record.
    """
    username = uuid.uuid4().hex

    UserModel = get_user_model()

    # Note that this could be accomplished in one try-except clause, but
    # instead we use get_or_create when creating unknown users since it has
    # built-in safeguards for multiple threads.
    user, created = UserModel.objects.get_or_create(**{
        UserModel.USERNAME_FIELD: username,
    })

    if created:
        logger.debug('authenticate created a new user for %s' % username)
    else:
        logger.debug('authenticate found an existing user for %s' % username)

    return user

class LTIRequestValidator(backends.LTIRequestValidator):
    @property
    def client_key_length(self):
        return 1,100

    @property
    def nonce_length(self):
        return 1,200

    @property
    def safe_characters(self):
        return set(UNICODE_ASCII_CHARACTER_SET+'-')

    def check_client_key(self, client_key):
        lower, upper = self.client_key_length
        return lower <= len(client_key) <= upper

    def validate_client_key(self,client_key,request):
        return LTI_11_Consumer.objects.filter(key=client_key).exists()

    def get_client_secret(self,client_key,request):
        try:
            consumer = LTI_11_Consumer.objects.get(key=client_key)
            return consumer.secret
        except LTIConsumer.DoesNotExist:
            return None

class LTI_11_AuthBackend(backends.LTIAuthBackend):
    validator_class = LTIRequestValidator

    def authenticate(self, request):
        request_key = request.POST.get('oauth_consumer_key', None)

        if request_key is None:
            return None

        validator = self.get_validator()
        endpoint = self.get_endpoint()

        secret = validator.get_client_secret(request_key,request)

        if secret is None:
            raise PermissionDenied

        headers = {k:v for k,v in request.META.items() if type(v)==str}
        for k,v in request.META.items():
            if k.lower() in ['content_type','content-type']:
                headers['Content-Type'] = v

        request_is_valid,_ = endpoint.validate_request(
            request.build_absolute_uri(),
            request.method,
            request.POST.dict(),
            headers
        )

        if not request_is_valid:
            raise PermissionDenied

        # if we got this far, the user is good

        user = None

        email = request.POST.get('lis_person_contact_email_primary')
        first_name = request.POST.get('lis_person_name_given','')[:30]
        last_name = request.POST.get('lis_person_name_family','')[:30]

        # Retrieve username from LTI parameter or default to an overridable function return value
        user_id = request.POST.get('user_id')

        # If there's a recorded alias to a User object with this consumer and user_id, return that user
        alias = LTI_11_UserAlias.objects.filter(consumer__lti_11__key=request_key, consumer_user_id=user_id).last()
        if alias is not None:
            user = alias.user
        # If no alias exists, get or create a user and make an alias record.
        else:
            consumer = LTIConsumer.objects.get(lti_11__key=request_key)

            user = new_lti_user()

            LTI_11_UserAlias.objects.create(consumer=consumer, user=user, consumer_user_id=user_id)

        # update the user
        if email:
            user.email = email
        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name
        user.save(update_fields=('email', 'first_name', 'last_name'))

        return user

    def clean_username(self, username):
        return username[:140]

    def get_default_username(self, request, prefix=''):
        """
        Return a default username value in case offical
        LTI param lis_person_sourcedid was not present.
        """
        # Default back to user_id lti param
        uname = request.POST.get('canvas_user_id') or request.POST.get('user_id')
        if uname is None:
            raise Exception("No user-identifying information is present in the LTI launch data")
        return prefix + uname

class LTI_13_AuthBackend(ModelBackend):
    tool_conf = DjangoDbToolConf()
    launch_data_storage = DjangoCacheDataStorage()
    message_launch_cls = DjangoMessageLaunch

    def get_message_launch(self, request):
        message_launch = self.message_launch = self.message_launch_cls(request, self.tool_conf, launch_data_storage = self.launch_data_storage)
        return message_launch

    def get_lti_tool(self, request):
        message_launch = self.get_message_launch(request)
        iss = self.message_launch.get_iss()
        client_id = self.message_launch.get_client_id()
        tool = self.message_launch.get_tool_conf().get_lti_tool(iss, client_id)
        return tool

    def authenticate(self, request):
        try:
            lti_tool = self.get_lti_tool(request)
            launch_data = self.message_launch.get_launch_data()
        except LtiException as e:
            return

        sub = launch_data.get('sub')
        
        try:
            user_alias = LTI_13_UserAlias.objects.get(consumer__lti_13__tool=lti_tool, sub=sub)
            user = user_alias.user
        except LTI_13_UserAlias.DoesNotExist:
            user = new_lti_user()

            consumer = lti_tool.numbas.consumer

            user_alias = LTI_13_UserAlias.objects.create(consumer=consumer, user=user, sub=sub)
        
        full_name = launch_data.get('name')
        if full_name:
            user_alias.full_name = full_name

        given_name = launch_data.get('given_name')
        if given_name:
            user_alias.given_name = given_name
            user.first_name = given_name

        family_name = launch_data.get('family_name')
        if family_name:
            user_alias.family_name = family_name
            user.last_name = family_name
        
        email = launch_data.get('email')
        if email:
            user_alias.email = email
            user.email = email

        locale = launch_data.get('locale')
        if locale:
            user_alias.locale = locale

        lis_claim = launch_data.get('https://purl.imsglobal.org/spec/lti/claim/lis')
        if lis_claim:
            user_alias.lis_person_sourcedid = lis_claim.get('person_sourcedid')

        user_alias.save(update_fields=('full_name', 'given_name', 'family_name', 'email', 'locale', 'lis_person_sourcedid'))
        user.save(update_fields=('first_name', 'last_name', 'email'))

        return user
