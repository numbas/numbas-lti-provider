"""
Rewind an attempt to a previous time.
Newer SCORM elements will be deleted.
"""

from django.db import transaction
from django.utils.timezone import datetime, make_aware
from django.core.management.base import BaseCommand

from numbas_lti.models import Attempt, ScormElement, ScormElementDiff, resolve_diffed_scormelements
from numbas_lti.tasks import scorm_set_score, scorm_set_completion_status, attempt_update_score_info, attempt_report_outcome

class Command(BaseCommand):
    help = "Rewind an attempt to a previous time. Newer SCORM elements will be deleted."

    def add_arguments(self, parser):
        parser.add_argument('attempt', help='The ID of the attempt to rewind.')
        parser.add_argument('time', help='The time to rewind to, in ISO format.')

    def handle(self, *args, **options):
        attempt_pk = options['attempt']

        attempt = Attempt.objects.get(pk=attempt_pk)

        time = make_aware(datetime.fromisoformat(options['time']))

        score = attempt.scormelements.filter(key='cmi.score.raw',time__lt=time).order_by('-time').first()
        score = float(score.value) if score is not None else 0

        print(f'Will delete attempt data for attempt {attempt} after time {time}. The score was {score}.')

        if input('Continue? [y/N] ') != 'y':
            return

        with transaction.atomic():
            new_last_suspend_data = attempt.scormelements.filter(time__lte=time, key='cmi.suspend_data').order_by('-time').first()
            if new_last_suspend_data is not None:
                resolved = resolve_diffed_scormelements(attempt.scormelements.filter(time__gte=new_last_suspend_data.time, key='cmi.suspend_data'))

                ScormElementDiff.objects.filter(element__in=resolved).delete()

                v = next((e for e in resolved if e.pk == new_last_suspend_data.pk))

                new_last_suspend_data.value = v.value
                new_last_suspend_data.save()

            attempt.scormelements.filter(time__gt=time).delete()

        scorm_set_score(attempt.scormelements.current('cmi.score.scaled'), fetch=True)

        scorm_set_completion_status(attempt.scormelements.current('cmi.completion_status'))

        attempt_update_score_info(attempt, attempt.question_numbers())

        if attempt.userscorereported_set.exists():
            attempt_report_outcome(attempt)
