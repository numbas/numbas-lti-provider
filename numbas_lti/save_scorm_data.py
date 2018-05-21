from .models import ScormElement
import datetime
from django.db.utils import OperationalError
from django.utils import timezone
import logging
import re

logger = logging.getLogger(__name__)

re_question_score_element = re.compile(r'cmi.objectives.(\d+).(?:score.(?:raw|scaled|max)|completion_status)')

def save_scorm_data(attempt,batches):
    done = []
    unsaved_elements = []
    question_scores_changed = set()
    for id,elements in batches.items():
        for element in elements:
            try:
                _, created = ScormElement.objects.get_or_create(
                    attempt = attempt,
                    key = element['key'],
                    value = element['value'],
                    time = timezone.make_aware(datetime.datetime.fromtimestamp(element['time'])),
                    counter = element.get('counter',0)
                )
                if created:
                    m = re_question_score_element.match(element['key'])
                    if m:
                        number = int(m.group(1))
                        question_scores_changed.add(number)
            except ScormElement.MultipleObjectsReturned:
                pass
            except OperationalError as e:
                if len(e.args)==2:
                    code, msg = e.args
                    if code in [1366]:
                        logger.exception(_("Error saving SCORM data via AJAX fallback for attempt {}:\n{}".format(attempt.pk,e)))
                        unsaved_elements.append(element)
                    else:
                        raise e
        done.append(id)

    for number in question_scores_changed:
        attempt.update_question_score_info(number)
    return done,unsaved_elements
