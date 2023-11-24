from .models import ScormElement
import datetime
from django.db import transaction
from django.db.utils import OperationalError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import logging
from pytz.exceptions import AmbiguousTimeError
import re

from . import tasks

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
                    try:
                        time = timezone.make_aware(datetime.datetime.fromtimestamp(element['time']))
                    except AmbiguousTimeError:
                        time = timezone.make_aware(datetime.datetime.fromtimestamp(element['time']), is_dst=False)

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

    update_question_score_info(attempt,new_elements)

    return done,unsaved_elements

re_question_score_element = re.compile(r'cmi.objectives.(\d+).(?:score.(?:raw|scaled|max)|completion_status)')
re_exam_score_element = re.compile(r'cmi.score.(raw|scaled)')

def update_question_score_info(attempt,elements):
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
