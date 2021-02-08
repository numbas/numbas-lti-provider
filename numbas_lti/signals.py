from django.dispatch import receiver
from django.conf import settings
from django.db import models
from channels import Group, Channel
from django.utils import timezone
from datetime import datetime

from .groups import group_for_resource
from .report_outcome import report_outcome
from .models import Exam, ScormElement, EditorLink, Resource, Attempt, ExtractPackage

import os
import shutil
from zipfile import ZipFile
from lxml import etree
import re
import json

USE_HUEY = 'huey.contrib.djhuey' in settings.INSTALLED_APPS

if USE_HUEY:
    from . import tasks

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
    resource = instance
    group = group_for_resource(resource)
    group.send({"text": json.dumps({'availability_dates': resource.availability_json()})})

"""
# Removed because it might be killing the server
@receiver(models.signals.post_save,sender=AttemptQuestionScore)
def question_score_live_stats(sender,instance,**kwargs):
    resource = instance.attempt.resource
    group = group_for_resource_stats(resource)
    group.send({"text": json.dumps(resource.live_stats_data())})
"""

@receiver(models.signals.post_save,sender=ScormElement)
def send_scorm_element_to_dashboard(sender,instance,created,**kwargs):
    Group(instance.attempt.channels_group()).send({
        "text": json.dumps(instance.as_json())
    })

@receiver(models.signals.post_save,sender=ScormElement)
def scorm_set_score(sender,instance,created,**kwargs):
    if instance.key!='cmi.score.scaled' or not created:
        return

    if not (instance.attempt.scaled_score_element is None or instance.newer_than(instance.attempt.scaled_score_element)):
        return

    instance.attempt.scaled_score = float(instance.value)
    instance.attempt.scaled_score_element = instance
    instance.attempt.save(update_fields=['scaled_score','scaled_score_element'])
    if instance.attempt.resource.report_mark_time == 'immediately':
        if USE_HUEY:
            tasks.attempt_report_outcome(instance.attempt)
        else:
            Channel('report.attempt').send({'pk':instance.attempt.pk})

@receiver(models.signals.post_save,sender=ScormElement)
def scorm_set_completion_status(sender,instance,created,**kwargs):
    if instance.key!='cmi.completion_status' or not created:
        return

    if not (instance.attempt.completion_status_element is None or instance.newer_than(instance.attempt.completion_status_element)):
        return


    instance.attempt.completion_status = instance.value
    instance.attempt.completion_status_element = instance
    update_fields = ['completion_status','completion_status_element']
    if instance.attempt.completion_status == 'incomplete':
        instance.attempt.end_time = None
        update_fields.append('end_time')
    instance.attempt.save(update_fields=update_fields)

    if instance.attempt.resource.report_mark_time == 'oncompletion' and instance.value=='completed':
        if USE_HUEY:
            tasks.attempt_report_outcome(instance.attempt)
        else:
            Channel('report.attempt').send({'pk':instance.attempt.pk})

@receiver(models.signals.post_save,sender=ScormElement)
def scorm_set_start_time(sender,instance,created,**kwargs):
    if instance.key != 'cmi.suspend_data':
        return

    try:
        data = json.loads(instance.value)
        if data['start'] is not None:
            start_time = timezone.make_aware(datetime.fromtimestamp(data['start']/1000))
        else:
            return
    except (json.JSONDecodeError, KeyError):
        return

    if start_time != instance.attempt.start_time:
        instance.attempt.start_time = start_time
        instance.attempt.save(update_fields=['start_time'])

@receiver(models.signals.post_save,sender=Attempt)
def send_receipt_on_completion(sender,instance, **kwargs):
    try:
        attempt = Attempt.objects.get(pk=instance.pk)
    except Attempt.DoesNotExist:
        return
    if getattr(settings,'EMAIL_COMPLETION_RECEIPTS',False) and attempt.resource.email_receipts:
        if attempt.all_data_received and attempt.end_time is not None and attempt.completion_status=='completed' and not attempt.sent_receipt:
            if USE_HUEY:
                tasks.send_attempt_completion_receipt(attempt)
            else:
                Channel('attempt.email_receipt').send({'pk': attempt.pk})


@receiver(models.signals.post_save,sender=ScormElement)
def scorm_set_num_questions(sender,instance,created,**kwargs):
    """ Set the number of questions for this resource - can only work this out once the exam has been run! """
    if not re.match(r'^cmi.objectives.([0-9]+).id$',instance.key) or not created:
        return

    number = int(re.match(r'q(\d+)',instance.value).group(1))+1
    resource = instance.attempt.resource
    
    if number>resource.num_questions:
        resource.num_questions = number
        resource.save(update_fields=['num_questions'])

@receiver(models.signals.pre_save,sender=EditorLink)
def update_editor_cache_before_save(sender,instance,**kwargs):
    exams = instance.available_exams

