from .models import ScormElement
import datetime
from django.db.utils import OperationalError
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

def save_scorm_data(attempt,batches):
    done = []
    unsaved_elements = []
    for id,elements in batches.items():
        for element in elements:
            try:
                ScormElement.objects.get_or_create(
                    attempt = attempt,
                    key = element['key'],
                    value = element['value'],
                    time = timezone.make_aware(datetime.datetime.fromtimestamp(element['time'])),
                    counter = element.get('counter',0)
                )
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
    return done,unsaved_elements
