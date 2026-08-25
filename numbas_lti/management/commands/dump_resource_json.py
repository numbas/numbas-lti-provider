from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
import os
import json
from pathlib import Path
import subprocess
import datetime
from django.utils.timezone import now
import uuid

from numbas_lti.models import Resource, Attempt, ScormElement, FileReport
from numbas_lti.tasks import resource_json_dump_report

class Command(BaseCommand):
    help = 'Make a JSON dump of resource data'

    def add_arguments(self, parser):
        parser.add_argument('resource_pk',type=int)
        parser.add_argument('--full',dest='save',action='store_true')

    def handle(self, *args, **options):
        self.options = options
        resource_pk = options['resource_pk']

        resource = Resource.objects.get(pk=resource_pk)
        print(f"Dumping {resource}")

        filename = '{slug}-attempts_data-{date}-{uuid}.json'.format(
            slug = resource.slug,
            date = now().strftime('%Y-%m-%d-%H_%M_%S'),
            uuid = uuid.uuid4().hex[:8]
        )
        outpath = Path(settings.MEDIA_ROOT) / 'reports' / filename

        domain = getattr(settings, 'ALLOWED_HOSTS', ['localhost'])[0]

        with open(outpath, 'w') as f:
            resource.json_dump(f, full=True)

        print(f'The file has been saved at {outpath}')
        print(f'The URL might be https://{domain}{settings.MEDIA_URL}{outpath.relative_to(settings.MEDIA_ROOT)}')
