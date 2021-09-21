from datetime import datetime
from django.db.models import Count
from django.utils import timezone
from huey import crontab
from huey.contrib.djhuey import periodic_task, task
import json
import logging
from numbas_lti.report_outcome import ReportOutcomeException
from numbas_lti.models import Attempt, ScormElement, diff_scormelements
import time

logger = logging.getLogger(__name__)

@task(priority=1)
def editorlink_update_cache(el):
    logger.debug(f"Update the editor link {el}")
    el.update_cache()
    el.save()

@task(priority=300)
def send_attempt_completion_receipt(attempt):
    logger.debug(f"Send a completion receipt for attempt {attempt}")
    attempt.send_completion_receipt()

@task(priority=200)
def resource_report_scores(resource):
    logger.debug(f"Report scores for resource {resource}")
    resource.report_scores()

@task(priority=200)
def attempt_report_outcome(attempt):
    logger.debug(f"Report score for attempt {attempt}")
    time.sleep(0.1)
    try:
        attempt.report_outcome()
    except ReportOutcomeException:
        pass

@periodic_task(crontab(minute='*'),priority=0)
def diff_suspend_data():
    logger.debug("Diff suspend data")
    attempts = Attempt.objects.filter(diffed=False)
    MAX_TIME = 10
    start = datetime.now()
    num_diffed = 0
    if attempts.exists():
        for a in attempts:
            diff_scormelements(a)
            t2 = datetime.now()
            num_diffed += 1
            if (t2-start).total_seconds()>MAX_TIME:
                break
    logger.debug(f"Diffed {num_diffed} attempts")

@task(priority=10)
def scorm_set_score(attempt):
    logger.debug(f"Set score for attempt {attempt}")
    e = attempt.scormelements.current('cmi.score.scaled')

    try:
        score = float(e.value)
    except ValueError:
        return

    if score == attempt.scaled_score:
        return

    attempt.scaled_score_element = e
    attempt.scaled_score = score
    attempt.save(update_fields=['scaled_score', 'scaled_score_element'])

    if attempt.resource.report_mark_time == 'immediately':
        attempt_report_outcome(attempt)

@task(priority=10)
def scorm_set_completion_status(attempt):
    logger.debug(f"Set completion status for attempt {attempt}")
    e = attempt.scormelements.current('cmi.completion_status')

    if e.value == attempt.completion_status:
        return
    
    attempt.completion_status = e.value
    attempt.completion_status_element = e
    update_fields = ['completion_status','completion_status_element']
    if attempt.completion_status == 'incomplete':
        attempt.end_time = None
        update_fields.append('end_time')
    attempt.save(update_fields=update_fields)

    if attempt.resource.report_mark_time == 'oncompletion' and attempt.completion_status=='completed':
        tasks.attempt_report_outcome(attempt)

@task(priority=9)
def scorm_set_start_time(attempt):
    logger.debug(f"Set start time for attempt {attempt}")
    e = attempt.scormelements.current('cmi.suspend_data')

    try:
        data = json.loads(e.value)
        if data['start'] is not None:
            start_time = timezone.make_aware(datetime.fromtimestamp(float(data['start'])/1000))
        else:
            return
    except (json.JSONDecodeError, KeyError):
        return

    if start_time == attempt.start_time:
        return

    attempt.start_time = start_time
    attempt.save(update_fields=['start_time'])

@task(priority=9)
def scorm_set_num_questions(resource,number):
    logger.debug(f"Set num questions for resource {resource} to {number}")
    if number>resource.num_questions:
        resource.num_questions = number
        resource.save(update_fields=['num_questions'])
