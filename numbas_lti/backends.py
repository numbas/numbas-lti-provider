from django_auth_lti import backends
from numbas_lti.models import LTIConsumer
from oauthlib.oauth1.rfc5849.utils import UNICODE_ASCII_CHARACTER_SET

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
        return LTIConsumer.objects.filter(key=client_key).exists()

    def get_client_secret(self,client_key,request):
        try:
            consumer = LTIConsumer.objects.get(key=client_key)
            return consumer.secret
        except LTIConsumer.DoesNotExist:
            return None

class LTIAuthBackend(backends.LTIAuthBackend):
    validator_class = LTIRequestValidator
