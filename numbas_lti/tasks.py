import csv
from datetime import datetime, timedelta
from django.conf import settings
from django.contrib import messages
from django.db.models import Count
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from functools import wraps
from huey import crontab
from huey.contrib.djhuey import periodic_task, task, db_periodic_task, db_task
import json
import logging
from numbas_lti.report_outcome import ReportOutcomeException
from numbas_lti.models import Attempt, ScormElement, diff_scormelements, FileReport, EditorLink, Resource
import re

logger = logging.getLogger(__name__)

@db_task(priority=1)
def editorlink_update_cache(el):
    logger.debug(f"Update the editor link {el}")
    el = EditorLink.objects.get(pk=el.pk)
    el.update_cache()
    el.save()

@db_task(priority=300)
def send_attempt_completion_receipt(attempt):
    logger.debug(f"Send a completion receipt for attempt {attempt}")
    attempt = Attempt.objects.get(pk=attempt.pk)
    attempt.send_completion_receipt()

@db_task(priority=200)
def resource_report_scores(resource):
    logger.debug(f"Report scores for resource {resource}")
    resource = Resource.objects.get(pk=resource.pk)
    resource.report_scores()

@db_task(priority=200)
def attempt_report_outcome(attempt):
    logger.debug(f"Report score for attempt {attempt}")
    attempt = Attempt.objects.get(pk=attempt.pk)
    try:
        attempt.report_outcome()
    except ReportOutcomeException:
        pass

@db_periodic_task(crontab(minute='*'),priority=0)
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
def scorm_set_score(element, fetch=False):
    attempt = element.attempt

    if fetch:
        try:
            element = attempt.scormelements.current('cmi.score.scaled')
        except ScormElement.DoesNotExist:
            return

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
        attempt_report_outcome.schedule((attempt,),delay=0.1)

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
        attempt.save(update_fields=['scaled_score'])

@db_task(priority=15)
def resource_update_score_info(resource):
    changed_questions = list(range(resource.num_questions))
    for attempt in resource.attempts.all():
        attempt_update_score_info(attempt,changed_questions)

def report_task(writer):
    """ 
    Make a task which completes a report file.
    """
    @db_task(priority=50)
    @wraps(writer)
    def file_report(fr,**kwargs):
        try:
            with open(fr.outfile.path,'w') as f:
                writer(fr,f,**kwargs)
            fr.status = 'complete'
            fr.save()
        except Exception as e:
            print("ERROR")
            import traceback
            traceback.print_exception(e)
            fr.status = 'error'
            fr.save()

    return file_report

def fixtime(cell):
    if isinstance(cell,datetime):
        return cell.astimezone(timezone.get_current_timezone()).isoformat()
    else:
        return cell

def fixrow(row):
    return [fixtime(c) for c in row]

def csv_report_task(row_iterator):
    @report_task
    @wraps(row_iterator)
    def write_csv(fr,f):
        csv_writer = csv.writer(f)
        for row in row_iterator(fr):
            csv_writer.writerow(fixrow(row))
 
    return write_csv

@csv_report_task
def resource_scores_csv_report(fr):
    logger.debug(f"Create scores CSV report {fr}")
    resource = fr.resource

    headers = [_(x) for x in ['First name','Last name','Email','Username','Percentage','Raw score', 'Max score']]
    yield headers

    for student in resource.students().all():
        user_data = resource.user_data(student)
        username = '' if user_data is None else user_data.get_source_id()
        attempt, completion_status = resource.grade_user(student)
        scaled_score = attempt.scaled_score
        student_attempts = resource.attempts.filter(user=student)
        max_score = max(a.max_score for a in student_attempts) if student_attempts.exists() else 0
        raw_score = scaled_score * max_score    # This might introduce a rounding error
        yield (
            student.first_name,
            student.last_name,
            student.email,
            username,
            scaled_score*100,
            raw_score,
            max_score
        )

@csv_report_task
def resource_attempts_csv_report(fr):
    resource = fr.resource
    num_questions = resource.num_questions

    headers = [_(x) for x in ['First name','Last name','Email','Username','Start time','End time','Time spent','Completed?','Total score','Percentage']]+[_('Question {n}').format(n=i+1) for i in range(num_questions)]
    yield headers

    for attempt in resource.attempts.all():
        user_data = resource.user_data(attempt.user)
        username = '' if user_data is None else user_data.get_source_id()
        row = [
            attempt.user.first_name,
            attempt.user.last_name,
            attempt.user.email,
            username,
            attempt.start_time,
            attempt.end_time,
            attempt.time_spent(),
            attempt.completion_status,
            attempt.raw_score,
            attempt.scaled_score*100,
        ]+[attempt.question_raw_score(n) for n in range(num_questions)]
        yield row

@report_task
def resource_json_dump_report(fr,f,full=False):
    resource = fr.resource
    
    f.write('''{{
    "resource": {{
        "pk": {pk},
        "title": {title}
    }},
    "attempts": ['''.format(pk=resource.pk,title=json.dumps(resource.title)))

    for i,a in enumerate(resource.attempts.all()):
        if i>0:
            f.write(',')
        f.write(json.dumps(a.data_dump(include_all_scorm=full)))

    f.write(']\n}')

@db_periodic_task(crontab(hour='*'),priority=0)
def delete_old_reports():
    expiry_date = timezone.make_aware(datetime.now() - timedelta(days=settings.REPORT_FILE_EXPIRY_DAYS))
    FileReport.objects.filter(creation_time__lt=expiry_date).delete()

@db_task(priority=1)
def fetch_lti_13_ags_lineitems(context):
    """
        Update the cached list of AGS lineitems for an LTI 1.3 context.
    """
    context.lti_13.ags_lineitems(force_fetch=True)
