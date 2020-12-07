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

    def add_arguments(self, parser):
        parser.add_argument('resource_pk',type=int)
        parser.add_argument('--save',dest='save',action='store_true')
        parser.add_argument('--attempts',nargs='+',dest='attempt_pks')
        parser.add_argument('--show-all-scores',dest='show_all_scores',action='store_true')
        parser.add_argument('--unsubmitted',dest='unsubmitted',action='store_true')

    def handle(self, *args, **options):
        self.options = options
        resource_pk = options['resource_pk']

        resource = Resource.objects.get(pk=resource_pk)
        print("Remarking {}".format(resource))

        try:
            if self.options['attempt_pks']:
                attempts = resource.attempts.filter(pk__in=self.options['attempt_pks'])
            else:
                attempts = resource.attempts.all()
            results = remark_attempts(resource.exam, attempts, apply_unsubmitted_answers=options['unsubmitted'])
            print(len(results['results']),'results')
            for result in results['results']:
                self.update_attempt(result)
        except ExamTestException as e:
            print(e)

    def update_attempt(self, result):
        t = now()
        if not result.get('success'):
            print("Attempt {} by {} failed.".format(attempt.pk, attempt.user.get_full_name()))
        changed_keys = result.get('changed_keys',[])
        attempt = Attempt.objects.get(pk=result['attempt_pk'])
        old_scaled_score = attempt.scaled_score
        old_raw_score = attempt.raw_score
        for key,value in changed_keys.items():
            if key in self.remark_ignore_keys:
                continue
            if self.options['save']:
                e = ScormElement.objects.create(
                    attempt = attempt,
                    key = key,
                    value = value,
                    time = t,
                    counter = 0
                )
                RemarkedScormElement.objects.create(element=e,user=None)
        if self.options['save']:
            new_raw_score = attempt.raw_score
        else:
            new_raw_score = float(changed_keys.get('cmi.score.raw',old_raw_score))
        if self.options['show_all_scores'] or old_raw_score != new_raw_score:
            print("Attempt {pk} by {name}: score was {old_raw_score}, is now {new_raw_score} ({change_description}).".format(
                pk = attempt.pk,
                name = attempt.user.get_full_name(),
                old_raw_score = old_raw_score,
                new_raw_score = new_raw_score,
                change_description = '\033[32mincrease\033[0m' if new_raw_score>old_raw_score else '\033[31mdecrease\033[0m' if new_raw_score<old_raw_score else 'unchanged'
            ))
