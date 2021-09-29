from datetime import datetime
from django.db.models import Count
from django.utils import timezone
from huey import crontab
from huey.contrib.djhuey import periodic_task, task, db_periodic_task, db_task
import json
import logging
from numbas_lti.report_outcome import ReportOutcomeException
from numbas_lti.models import Attempt, ScormElement, diff_scormelements
import re

logger = logging.getLogger(__name__)

@db_task(priority=1)
def editorlink_update_cache(el):
    logger.debug(f"Update the editor link {el}")
    el.update_cache()
    el.save()

@db_task(priority=300)
def send_attempt_completion_receipt(attempt):
    logger.debug(f"Send a completion receipt for attempt {attempt}")
    attempt.send_completion_receipt()

@db_task(priority=200)
def resource_report_scores(resource):
    logger.debug(f"Report scores for resource {resource}")
    resource.report_scores()

@db_task(priority=200)
def attempt_report_outcome(attempt):
    logger.debug(f"Report score for attempt {attempt}")
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

@db_task(priority=10)
def scorm_set_score(element):
    attempt = element.attempt

    logger.debug(f"Set score for attempt {attempt}")
    try:
        score = float(element.value)
    except ValueError:
        return

    if score == attempt.scaled_score:
        return

    attempt.scaled_score_element = element
    attempt.scaled_score = score
    attempt.save(update_fields=['scaled_score', 'scaled_score_element'])

    if attempt.resource.report_mark_time == 'immediately':
        attempt_report_outcome.schedule((attempt,),delay=0.1)

@db_task(priority=10)
def scorm_set_completion_status(element):
    attempt = element.attempt

    logger.debug(f"Set completion status for attempt {attempt}")

    if element.value == attempt.completion_status:
        return
    
    attempt.completion_status = element.value
    attempt.completion_status_element = element
    update_fields = ['completion_status','completion_status_element']
    if attempt.completion_status == 'incomplete':
        attempt.end_time = None
        update_fields.append('end_time')
    attempt.save(update_fields=update_fields)

    if attempt.resource.report_mark_time == 'oncompletion' and attempt.completion_status=='completed':
        tasks.attempt_report_outcome.schedule((attempt,),delay=0.1)

@db_task(priority=9)
def scorm_set_start_time(element):
    attempt = element.attempt

    logger.debug(f"Set start time for attempt {attempt}")

    try:
        data = json.loads(element.value)
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

@db_task(priority=9)
def scorm_set_num_questions(resource,number):
    logger.debug(f"Set num questions for resource {resource} to {number}")
    if number>resource.num_questions:
        resource.num_questions = number
        resource.save(update_fields=['num_questions'])

@db_task(priority=20)
def attempt_update_score_info(attempt,question_scores_changed):
    for number in question_scores_changed:
        attempt.update_question_score_info(number)

    if attempt.max_score>0:
        scaled_score = attempt.raw_score/attempt.max_score if attempt.max_score != 0 else 0
    else:
        scaled_score = 0
    if scaled_score != attempt.scaled_score:
        attempt.scaled_score = scaled_score
        attempt.save()

@db_task(priority=15)
def resource_update_score_info(resource):
    changed_questions = list(range(resource.num_questions))
    for attempt in resource.attempts.all():
        attempt_update_score_info(attempt,changed_questions)
