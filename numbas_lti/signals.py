from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from datetime import timedelta
from django.dispatch import receiver
from django.conf import settings
from django.db import models
from django.contrib.auth.models import User
from huey.contrib.djhuey import HUEY
import logging
from lxml import etree
import os
import re
import shutil
from zipfile import ZipFile

from . import tasks
from .groups import group_for_resource, group_for_attempt
from .report_outcome import report_outcome
from .models import Exam, ScormElement, Resource, Attempt, ExtractPackage, FileReport, LTI_13_Context, LTI_13_ResourceLink, AccessChange


logger = logging.getLogger(__name__)

AUTOMATIC_SCORE_REPORT_DELAY_MINUTES = timedelta(minutes=getattr(settings,'AUTOMATIC_SCORE_REPORT_DELAY_MINUTES', 5))

@receiver(models.signals.post_save)
def extract_package(sender,instance,**kwargs):
    if not issubclass(sender,ExtractPackage):
        return
    if os.path.exists(instance.extracted_path):
        shutil.rmtree(instance.extracted_path)
    os.makedirs(instance.extracted_path)
    z = ZipFile(instance.package.file,'r')
    z.extractall(instance.extracted_path)


@receiver(models.signals.pre_save, sender=Exam)
def set_exam_name_from_package(sender,instance,**kwargs):
    z = ZipFile(instance.package.file,'r')
    with z.open('imsmanifest.xml','r') as manifest_file:
        manifest = etree.parse(manifest_file)
    instance.title = manifest.find('.//ims:title',namespaces={'ims':'http://www.imsglobal.org/xsd/imscp_v1p1'}).text
    if not instance.retrieve_url:
        try:
            with z.open('downloaded-from.txt','r') as f:
                instance.retrieve_url = f.read().strip().decode('utf-8')
        except KeyError:
            pass

def cancel_tasks(predicate):
    for t in HUEY.scheduled():
        if predicate(t) and not HUEY.is_revoked(t):
            HUEY.revoke(t)

def schedule_report_for_access_change(ac):
    # Cancel any previously scheduled tasks to report scores for this access change.
    cancel_tasks(lambda t: t.name == 'access_change_report_scores' and t.kwargs['access_change'].pk == ac.pk)

    # If the access change changes the due date, schedule a task to report scores for affected users.
    due_date = ac.get_due_date()
    if due_date is not None and due_date != ac.resource.due_date:
        tasks.access_change_report_scores.schedule(kwargs={'access_change': ac, 'resource': ac.resource}, eta=due_date + AUTOMATIC_SCORE_REPORT_DELAY_MINUTES)

    # If an "available until" date is set, schedule the task.
    if ac.available_until is not None:
        tasks.access_change_report_scores.schedule(kwargs={'access_change': ac, 'resource': ac.resource}, eta=due_date + AUTOMATIC_SCORE_REPORT_DELAY_MINUTES)


@receiver(models.signals.post_save, sender=AccessChange)
def access_change_changed(sender, instance, **kwargs):
    schedule_report_for_access_change(instance)

@receiver(models.signals.pre_delete, sender=AccessChange)
def access_change_changed(sender, instance, **kwargs):
    cancel_tasks(lambda t: t.name == 'access_change_report_scores' and t.kwargs['access_change'].pk == instance.pk)

@receiver(models.signals.post_save,sender=Resource)
def resource_settings_changed(sender,instance,**kwargs):
    """
        Schedule a task to report all scores for this resource when the due date passes.
    """
    resource = instance

    # Cancel any previously scheduled resources of this task.
    cancel_tasks(lambda t: t.name == 'resource_report_scores' and t.kwargs['resource'].pk == resource.pk and t.kwargs.get('automatic'))

    # Only do this for resources whose scores are automatically reported back.
    if resource.report_mark_time not in ('immediately', 'oncompletion'):
        return

    # If a due date is set, schedule the task.
    if resource.due_date is not None:
        tasks.resource_report_scores.schedule(kwargs={'resource':resource, 'automatic': True}, eta=resource.due_date + AUTOMATIC_SCORE_REPORT_DELAY_MINUTES)

    # If an "available until" date is set, schedule the task.
    if resource.available_until is not None:
        tasks.resource_report_scores.schedule(kwargs={'resource':resource, 'automatic': True}, eta=resource.available_until + AUTOMATIC_SCORE_REPORT_DELAY_MINUTES)

    # Schedule tasks to report scores for any users with changed due dates.
    for ac in resource.access_changes.all():
        schedule_report_for_access_change(ac)


@receiver(models.signals.post_save,sender=Resource)
def resource_availability_changed(sender,instance,**kwargs):
    instance.send_access_changes()

@receiver(models.signals.post_save,sender=AccessChange)
def access_change_changes(sender,instance,**kwargs):
    instance.resource.send_access_changes()

@receiver(models.signals.post_delete,sender=AccessChange)
def access_change_deleted(sender,instance,**kwargs):
    instance.resource.send_access_changes()

@receiver(models.signals.post_save,sender=LTI_13_ResourceLink)
def fetch_context_lineitems(sender, instance, created, **kwargs):
    """
        When an LTI 1.3 resource link is created, update the context's list of line items.
    """
    if not created:
        return

    context = instance.context
    if not hasattr(context, 'lti_13'):
        return

    tasks.fetch_lti_13_ags_lineitems(context)

@receiver(models.signals.post_save,sender=Attempt)
def send_score_on_attempt_creation(sender, instance, created, **kwargs):
    if not created:
        return
    if instance.resource.report_mark_time == 'immediately':
        tasks.attempt_report_outcome.schedule((instance,), delay=0.1)

@receiver(models.signals.post_save,sender=Attempt)
def send_receipt_on_completion(sender,instance, **kwargs):
    try:
        attempt = Attempt.objects.get(pk=instance.pk)
    except Attempt.DoesNotExist:
        return
    if getattr(settings,'EMAIL_COMPLETION_RECEIPTS',False) and attempt.resource.email_receipts:
        if attempt.all_data_received and attempt.end_time is not None and attempt.completion_status=='completed' and not attempt.sent_receipt:
            tasks.send_attempt_completion_receipt.schedule((attempt,), delay=0.1)


@receiver(models.signals.pre_delete, sender=FileReport)
def delete_file_report(sender,instance,**kwargs):
    instance.outfile.delete()
