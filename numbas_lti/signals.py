from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.dispatch import receiver
from django.conf import settings
from django.db import models
from django.contrib.auth.models import User
import logging
from lxml import etree
import os
import re
import shutil
from zipfile import ZipFile

from . import tasks
from .groups import group_for_resource, group_for_attempt
from .report_outcome import report_outcome
from .models import Exam, ScormElement, Resource, Attempt, ExtractPackage, FileReport


logger = logging.getLogger(__name__)


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


@receiver(models.signals.post_save,sender=Resource)
def resource_availability_changed(sender,instance,**kwargs):
    instance.send_access_changes()

@receiver(models.signals.post_save,sender=ScormElement)
def send_scorm_element_to_dashboard(sender,instance,created,**kwargs):
    if not created:
        return
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(group_for_attempt(instance.attempt), {'type': 'scorm.new.element','element':instance.as_json()})

@receiver(models.signals.post_save,sender=Attempt)
def send_score_on_attempt_creation(sender, instance, created, **kwargs):
    if not created:
        return
    if instance.resource.report_mark_time == 'immediately':
        tasks.attempt_report_outcome(instance)

@receiver(models.signals.post_save,sender=Attempt)
def send_receipt_on_completion(sender,instance, **kwargs):
    try:
        attempt = Attempt.objects.get(pk=instance.pk)
    except Attempt.DoesNotExist:
        return
    if getattr(settings,'EMAIL_COMPLETION_RECEIPTS',False) and attempt.resource.email_receipts:
        if attempt.all_data_received and attempt.end_time is not None and attempt.completion_status=='completed' and not attempt.sent_receipt:
            tasks.send_attempt_completion_receipt(attempt)


@receiver(models.signals.post_save,sender=ScormElement)
def scorm_set_score(sender,instance,created,**kwargs):
    if instance.key!='cmi.score.scaled' or not created:
        return

    if not instance.newer_than(instance.attempt.scaled_score_element):
        return

    tasks.scorm_set_score(instance)

@receiver(models.signals.post_save,sender=ScormElement)
def scorm_set_completion_status(sender,instance,created,**kwargs):
    if instance.key!='cmi.completion_status' or not created:
        return

    if not instance.newer_than(instance.attempt.completion_status_element):
        return

    tasks.scorm_set_completion_status(instance)

@receiver(models.signals.post_save,sender=ScormElement)
def scorm_set_start_time(sender,instance,created,**kwargs):
    if instance.key != 'cmi.suspend_data' or not created:
        return

    tasks.scorm_set_start_time(instance)

@receiver(models.signals.post_save,sender=ScormElement)
def scorm_set_num_questions(sender,instance,created,**kwargs):
    """ Set the number of questions for this resource - can only work this out once the exam has been run! """
    if not re.match(r'^cmi.objectives.([0-9]+).id$',instance.key) or not created:
        return

    number = int(re.match(r'q(\d+)',instance.value).group(1))+1
    tasks.scorm_set_num_questions(instance.attempt.resource, number)

@receiver(models.signals.pre_delete, sender=FileReport)
def delete_file_report(sender,instance,**kwargs):
    instance.outfile.delete()
