from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
import datetime
from django.db import transaction
from django.db.utils import OperationalError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import logging
import re

from . import tasks
from .groups import group_for_resource, group_for_attempt
from .models import ScormElement

logger = logging.getLogger(__name__)

def save_scorm_data(attempt,batches):
    done = []
    unsaved_elements = []
    new_elements = []
    with transaction.atomic():
        needs_diff = False
        for id,elements in batches.items():
            for element in elements:

                if 'time_iso' in element:
                    time = datetime.datetime.fromisoformat(re.sub(r'Z$','+00:00',element['time_iso']))
                else:
                    # versions of the LTI provider before v3.4 returned the time as a timestamp without timezone info.
                    # In case there are still clients with that version of the SCORM API open, continue loading that.
                    time = timezone.make_aware(datetime.datetime.fromtimestamp(element['time']))

                if attempt.completion_status=='completed' and (attempt.end_time is None or time > attempt.end_time):
                    continue    # don't save new elements after the exam has been created

                try:
                    e, created = ScormElement.objects.get_or_create(
                        attempt = attempt,
                        key = element['key'],
                        value = element['value'],
                        time = time,
                        counter = element.get('counter',0)
                    )
                    if created:
                        new_elements.append(e)
                except ScormElement.MultipleObjectsReturned:
                    pass
                except OperationalError as e:
                    if len(e.args)==2:
                        code, msg = e.args
                        if code in [1366, 1267]:
                            logger.exception(_("Error saving SCORM data for attempt {}:\n{}".format(attempt.pk,e)))
                            unsaved_elements.append(element)
                        else:
                            raise e
                if element['key'] == 'cmi.suspend_data':
                    needs_diff = True
            done.append(id)

    if needs_diff:
        attempt.diffed = False
        attempt.save(update_fields=('diffed',))

    for fn in post_save_tasks:
        try:
            fn(attempt, new_elements)
        except Exception as e:
            print(e)

    return done,unsaved_elements

re_question_score_element = re.compile(r'cmi.objectives.(\d+).(?:score.(?:raw|scaled|max)|completion_status)')
re_exam_score_element = re.compile(r'cmi.score.(raw|scaled)')

post_save_tasks = []

def post_save_task(fn):
    post_save_tasks.append(fn)
    return fn

def handle_one_key(key):
    def decorator(fn):
        def handler(attempt, elements):
            try:
                element = next(reversed([e for e in elements if e.key == key]))
            except StopIteration:
                return

            fn(attempt, element)
        return handler

    return decorator

@post_save_task
def update_question_score_info(attempt, elements):
    question_scores_changed = set()
    exam_score_changed = False
    for e in elements:
        m = re_question_score_element.match(e.key)
        if m:
            number = int(m.group(1))
            question_scores_changed.add(number)
        elif re_exam_score_element.match(e.key):
            exam_score_changed = True

    if question_scores_changed or exam_score_changed:
        tasks.attempt_update_score_info(attempt,question_scores_changed)

@post_save_task
def send_scorm_elements_to_dashboard(attempt, elements):
    channel_layer = get_channel_layer()

    group = group_for_attempt(attempt)

    for element in elements:
        async_to_sync(channel_layer.group_send)(group, {'type': 'scorm.new.element','element':element.as_json()})

@post_save_task
@handle_one_key('cmi.score.scaled')
def set_score(attempt, element):
    tasks.scorm_set_score.schedule((element,), delay=0.1)
    tasks.scorm_set_score.schedule((element, True), delay=10)

@post_save_task
@handle_one_key('cmi.completion_status')
def set_completion_status(attempt, element):
    tasks.scorm_set_completion_status.schedule((element,), delay=0.1)

@post_save_task
@handle_one_key('cmi.suspend_data')
def set_start_time(attempt, element):
    tasks.scorm_set_start_time.schedule((element,), delay=0.1)

@post_save_task
def set_num_questions(attempt, elements):
    num_questions = 0
    for element in elements:
        if not re.match(r'^cmi.objectives.([0-9]+).id$', element.key):
            continue

        number = int(re.match(r'q(\d+)', element.value).group(1)) + 1
        num_questions = max(num_questions, number)

    if num_questions > 0:
        tasks.scorm_set_num_questions.schedule((attempt.resource, num_questions,), delay=0.1)
