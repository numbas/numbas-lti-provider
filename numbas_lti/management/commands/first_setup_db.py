import io
import json
import urllib.parse
from contextlib import redirect_stdout
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.core.management import call_command

class Command(BaseCommand):
    help = 'Setup the database, following the first_setup script.'

    domain = None
    dev = False
    values = None

    def add_arguments(self, parser):
        parser.add_argument('--dev', action='store_true')
        parser.add_argument('values')

    def handle(self, values, *args, **kwargs):
        stdout_f = io.StringIO()
        with redirect_stdout(stdout_f):
            self.values = json.loads(values)
            self.dev = kwargs.get('dev', False)

            call_command('check')

            call_command('migrate')

            self.setup_site()

            superusers = User.objects.filter(is_superuser = True)

            if not self.dev:
                call_command('collectstatic', '--noinput')

            if self.values.get('SU_CREATE'):
                self.create_superuser()

        stdout = stdout_f.getvalue()

        result = {
            'superusers': [u.username for u in superusers],
            'domain': self.domain,
            'stdout': stdout,
            'dev': self.dev,
        }

        print(json.dumps(result))

    def setup_site(self):
        domain = 'localhost' if self.dev else 'numbas.example.com'

        if not self.dev:
            domain = self.values.get('DOMAIN','localhost')

        try:
            url = urllib.parse.urlparse(domain)
            self.domain = url.netloc if url.netloc else domain
        except ValueError:
            self.domain = domain

    def create_superuser(self):
        username = self.values.get('SU_NAME')
        email = self.values.get('SU_EMAIL')
        password = self.values.get('SU_PASS')
        first_name = self.values.get('SU_FIRST_NAME')
        last_name = self.values.get('SU_LAST_NAME')
        try:
            u = User.objects.get(username = username)
            u.email = email
            u.set_password(password)
            u.first_name = first_name
            u.last_name = last_name
        except User.DoesNotExist:
            u = User.objects.create_superuser(
                username,
                email,
                password,
                first_name = first_name,
                last_name = last_name
            )
        u.save()
