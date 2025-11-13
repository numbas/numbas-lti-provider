from django.core.management.base import BaseCommand
import os
import json
import subprocess
import datetime
from django.utils.timezone import now
from itertools import count
from django.conf import settings
import redis

from numbas_lti.models import Resource, User
from numbas_lti.report_outcome import report_outcome

class Command(BaseCommand):
    help = 'See if there are any hanging requests'

    def handle(self, *args, **options):
        pool = redis.ConnectionPool.from_url(settings.CHANNEL_LAYERS['default']['CONFIG']['hosts'][0])
        c = redis.Redis.from_pool(pool)
        s = c.get('daphne_debug_request_count')
        requests = '0' if s is None else s.decode('utf-8')
        print(f'{requests} requests')
        res = c.xread({'daphne_debug': 0})
        for k, vs in res:
            print(f'{len(vs)} hanging requests')
            for rid,v in vs:
                print(v)
