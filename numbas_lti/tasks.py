from datetime import datetime
from django.db.models import Count
from huey import crontab
from huey.contrib.djhuey import periodic_task, task
import logging
from numbas_lti.report_outcome import ReportOutcomeException
from numbas_lti.models import Attempt, ScormElement, diff_scormelements
import time

logger = logging.getLogger(__name__)

@task(priority=1)
def editorlink_update_cache(el):
    el.update_cache()
    el.save()

@task(priority=300)
def send_attempt_completion_receipt(attempt):
    attempt.send_completion_receipt()

@task(priority=200)
def resource_report_scores(resource):
    resource.report_scores()

@task(priority=200)
def attempt_report_outcome(attempt):
    time.sleep(0.1)
    try:
        attempt.report_outcome()
    except ReportOutcomeException:
        pass

@periodic_task(crontab(minute='*'),priority=0)
def diff_suspend_data():
    logging.debug("Diff suspend data")
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
    logging.debug(f"Diffed {num_diffed} attempts")

@task(priority=100)
def email_receipt(attempt):
    if not attempt.sent_receipt:
        attempt.send_completion_receipt()
