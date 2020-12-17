from huey import crontab
from huey.contrib.djhuey import periodic_task, task
from numbas_lti.report_outcome import ReportOutcomeException

@task()
def editorlink_update_cache(el):
    el.update_cache()
    el.save()

@task()
def send_attempt_completion_receipt(attempt):
    attempt.send_completion_receipt()

@task()
def resource_report_scores(resource):
    resource.report_scores()

@task()
def attempt_report_outcome(attempt):
    try:
        attempt.report_outcome()
    except ReportOutcomeException:
        pass
