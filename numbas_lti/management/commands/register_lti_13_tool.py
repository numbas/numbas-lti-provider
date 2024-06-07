from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django_auth_lti.patch_reverse import reverse
import json

from numbas_lti.models import LTIConsumer, LTI_13_Consumer
from pylti1p3.dynamic_registration import generate_key_pair
from pylti1p3.contrib.django.lti1p3_tool_config.models import LtiTool, LtiToolKey

class Command(BaseCommand):
    help = 'Register a new LTI 1.3 platform.'

    def add_arguments(self, parser):
        parser.add_argument('--issuer')
        parser.add_argument('--title')
        parser.add_argument('--preset', dest='preset')
        parser.add_argument('--key-set-url')
        parser.add_argument('--auth-login-url')
        parser.add_argument('--client-id')
        parser.add_argument('--deployment-id')

    def handle(self, *args, **options):
        known_settings = settings.CANVAS_LTI_13_PRESETS

        preset = options['preset']
        if preset:
            settings = self.known_settings[preset]
        else:
            settings = {
                'issuer': options['issuer'],
                'key_set_url': options['key_set_url'],
                'auth_login_url': options['auth_login_url'],
            }

        issuer = settings['issuer']
        key_set_url = settings['key_set_url']
        auth_login_url = settings['auth_login_url']

        title = options['title']
        client_id = options['client_id']
        deployment_id = options['deployment_id']

        if title is None:
            title = input("Give a title for this consumer: ")

        if client_id is None:
            raise CommandError("You must give a client ID.")

        if deployment_id is None:
            raise CommandError("You must give a deployment ID.")

        private_key, public_key = generate_key_pair()

        key, created_key = LtiToolKey.objects.get_or_create(name=issuer, defaults = {'private_key': private_key, 'public_key': public_key})

        if created_key:
            print("Created a new key")

        tool = LtiTool.objects.create(
            title=title,
            issuer=issuer,
            auth_login_url=auth_login_url,
            key_set_url=key_set_url,
            tool_key=key,
            client_id=client_id,
            deployment_ids = json.dumps([deployment_id])
        )

        consumer = LTIConsumer.objects.create()
        lti_13_consumer = LTI_13_Consumer.objects.create(consumer=consumer, tool=tool)

        print(f"Created a new consumer: {consumer.get_absolute_url()}")

