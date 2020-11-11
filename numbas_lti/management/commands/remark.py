from django.core.management.base import BaseCommand
import os
import json
import subprocess
import datetime
from django.utils.timezone import now

from numbas_lti.models import Resource, Attempt, ScormElement
from numbas_lti.test_exam import remark_attempts, ExamTestException

class Command(BaseCommand):
    help = 'Remark a resource'

    ignore_keys = ['cmi.suspend_data']

    def add_arguments(self, parser):
        parser.add_argument('resource_pk',type=int)
        parser.add_argument('--save',dest='save',action='store_true')

    def handle(self, *args, **options):
        self.options = options
        resource_pk = options['resource_pk']

        resource = Resource.objects.get(pk=resource_pk)
        print("Remarking {}".format(resource))

        try:
            results = remark_attempts(resource.exam)
            for result in results['results']:
                self.update_attempt(result)
        except ExamTestException as e:
            print(e)

    def update_attempt(self, result):
        t = now()
        changed_keys = result.get('changed_keys',[])
        attempt = Attempt.objects.get(pk=result['attempt_pk'])
        old_scaled_score = attempt.scaled_score
        old_raw_score = attempt.raw_score
        for key,value in changed_keys.items():
            if key in self.ignore_keys:
                continue
            if self.options['save']:
                ScormElement.objects.create(
                    attempt = attempt,
                    key = key,
                    value = value,
                    time = t,
                    counter = 0
                )
        if self.options['save']:
            new_raw_score = attempt.raw_score
        else:
            new_raw_score = float(changed_keys.get('cmi.score.raw',old_raw_score))
        if new_raw_score != old_raw_score:
            print("Attempt {} by {}: score was {}, is now {}.".format(attempt.pk, attempt.user.get_full_name(), old_raw_score, new_raw_score))
