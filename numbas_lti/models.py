from django.conf import settings
from django.db import models
from django.dispatch import receiver
from django.contrib.auth.models import User
import requests
from django.utils.text import slugify
from django.utils.translation import ugettext_lazy as _

from .report_outcome import report_outcome

import os
import shutil
from zipfile import ZipFile
from lxml import etree
import re

class LTIConsumer(models.Model):
    key = models.CharField(max_length=100)
    secret = models.CharField(max_length=100)

    def __str__(self):
        return self.key

class ExtractPackageMixin(object):
    extract_folder = 'extracted_zips'

    @property
    def extracted_path(self):
        return os.path.join(settings.MEDIA_ROOT,self.extract_folder,self.__class__.__name__,str(self.pk))

    @property
    def extracted_url(self):
        return '{}{}/{}/{}'.format(settings.MEDIA_URL,self.extract_folder,self.__class__.__name__,str(self.pk))

@receiver(models.signals.post_save)
def extract_package(sender,instance,**kwargs):
    if not issubclass(sender,ExtractPackageMixin):
        return
    if os.path.exists(instance.extracted_path):
        shutil.rmtree(instance.extracted_path)
    os.makedirs(instance.extracted_path)
    z = ZipFile(instance.package.file,'r')
    z.extractall(instance.extracted_path)


# Create your models here.
class Exam(ExtractPackageMixin,models.Model):
    title = models.CharField(max_length=300)
    package = models.FileField(upload_to='exams/')

    def __str__(self):
        return self.title

@receiver(models.signals.pre_save, sender=Exam)
def set_exam_name_from_package(sender,instance,**kwargs):
    z = ZipFile(instance.package.file,'r')
    with z.open('imsmanifest.xml','r') as manifest_file:
        manifest = etree.parse(manifest_file)
    instance.title = manifest.find('.//ims:title',namespaces={'ims':'http://www.imsglobal.org/xsd/imscp_v1p1'}).text


GRADING_METHODS = [
    ('highest',_('Highest score')),
    ('last',_('Last attempt')),
]

REPORT_TIMES = [
    ('immediately',_('Immediately')),
    ('oncompletion',_('On completion')),
    ('manually',_('Manually, by instructor')),
]
REPORTING_STATUSES = [
    ('reporting',_('Reporting scores')),
    ('error',_('Error encountered')),
    ('complete',_('All scores reported')),
]

class Resource(models.Model):
    resource_link_id = models.CharField(max_length=300)
    tool_consumer_instance_guid = models.CharField(max_length=300)
    exam = models.ForeignKey(Exam,blank=True,null=True,on_delete=models.SET_NULL)

    grading_method = models.CharField(max_length=20,choices=GRADING_METHODS,default='highest',verbose_name=_('Grading method'))
    include_incomplete_attempts = models.BooleanField(default=True,verbose_name=_('Include incomplete attempts in grading?'))
    show_incomplete_marks = models.BooleanField(default=True,verbose_name=_('Show score of in-progress attempts to students?'))
    report_incomplete_marks = models.BooleanField(default=True,verbose_name=_('Count scores for incomplete attempts?'))
    report_mark_time = models.CharField(max_length=20,choices=REPORT_TIMES,default='immediately',verbose_name=_('When to report scores back'))

    max_attempts = models.PositiveIntegerField(default=0,verbose_name=_('Maximum attempts per user'))

    def __str__(self):
        if self.exam:
            return str(self.exam)
        else:
            return _('{} {} - no exam uploaded').format(self.tool_consumer_instance_guid,self.resource_link_id)

    @property
    def slug(self):
        if self.exam:
            return slugify(self.exam.title)
        else:
            return 'resource'

    def grade_user(self,user):
        methods = {
            'highest': self.grade_highest,
            'last': self.grade_last,
        }
        attempts = self.attempts.filter(user=user)
        if not self.report_incomplete_marks:
            attempts = attempts.filter(completion_status='completed')
        if not self.include_incomplete_attempts:
            attempts = attempts.filter(completion_status='completed')
        if not attempts.exists():
            return 0
        return methods[self.grading_method](user,attempts)

    def grade_highest(self,user,attempts):
        return attempts.aggregate(highest_score=models.Max('scaled_score'))['highest_score']

    def grade_last(self,user,attempts):
        return attempts.order_by('-start_time').first()

    def students(self):
        return User.objects.filter(attempts__resource=self).distinct().order_by('last_name','first_name')

    def can_start_new_attempt(self,user):
        if self.max_attempts==0:
            return True
        return self.attempts.filter(user=user).count()<self.max_attempts or AccessToken.objects.filter(resource=self,user=user).exists()

    def num_questions(self):
        re_objective_id_key = r'^cmi.objectives.(\d+).id$'
        top_key = ScormElement.objects.filter(attempt__resource=self,key__regex=re_objective_id_key).aggregate(models.Max('key'))['key__max']
        if top_key is None:
            return 0
        else:
            n = re.match(re_objective_id_key,top_key).group(1)
            return int(n)+1

class ReportProcess(models.Model):
    resource = models.ForeignKey(Resource,on_delete=models.CASCADE,related_name='report_processes')
    status = models.CharField(max_length=10,choices=REPORTING_STATUSES,default='reporting',verbose_name=_("Current status of the process"))
    time = models.DateTimeField(auto_now_add=True,verbose_name=_("Time the reporting process started"))
    response = models.TextField(blank=True,verbose_name=_("Description of any error"))
    dismissed = models.BooleanField(default=False,verbose_name=_('Has the result of this process been dismissed by the instructor?'))

    class Meta:
        ordering = ['-time',]

COMPLETION_STATUSES = [
    ('not attempted',_('Not attempted')),
    ('incomplete',_('Incomplete')),
    ('completed',_('Complete')),
]

class AccessToken(models.Model):
    user = models.ForeignKey(User,on_delete=models.CASCADE,related_name='access_tokens')
    resource = models.ForeignKey(Resource,on_delete=models.CASCADE,related_name='access_tokens')

class LTIUserData(models.Model):
    user = models.ForeignKey(User,on_delete=models.CASCADE,related_name='lti_data')
    resource = models.ForeignKey(Resource,on_delete=models.CASCADE)
    lis_result_sourcedid = models.CharField(max_length=200,default='',blank=True,null=True)
    lis_outcome_service_url = models.TextField(default='',blank=True,null=True)
    last_reported_score = models.FloatField(default=0)

class AttemptManager(models.Manager):
    def get_queryset(self):
        return super(AttemptManager,self).get_queryset().filter(deleted=False)

class Attempt(models.Model):
    resource = models.ForeignKey(Resource,on_delete=models.CASCADE,related_name='attempts')
    exam = models.ForeignKey(Exam,on_delete=models.CASCADE,related_name='attempts')  # need to keep track of both resource and exam in case the exam later gets overwritten
    user = models.ForeignKey(User,on_delete=models.CASCADE,related_name='attempts')
    start_time = models.DateTimeField(auto_now_add=True)

    completion_status = models.CharField(max_length=20,choices=COMPLETION_STATUSES,default='not attempted')
    scaled_score = models.FloatField(default=0)

    deleted = models.BooleanField(default=False)

    objects = AttemptManager()

    class Meta:
        ordering = ['-start_time',]

    def get_element_default(self,key,default=None):
        try:
            return self.scormelements.current(key).value
        except ScormElement.DoesNotExist:
            return default

    def completed(self):
        return self.completion_status=='completed'

    @property
    def raw_score(self):
        return float(self.get_element_default('cmi.score.raw',0))

    @property
    def max_score(self):
        return float(self.get_element_default('cmi.score.max',0))

    def question_score(self,n):
        try:
            element = self.scormelements.current('cmi.objectives.{}.score.raw'.format(n))
            return element.value
        except ScormElement.DoesNotExist:
            return 0

class ScormElementQuerySet(models.QuerySet):
    def current(self,key):
        """ Return the last value of this field """
        elements = self.filter(key=key).order_by('-time')
        if not elements.exists():
            raise ScormElement.DoesNotExist()
        else:
            return elements.first()

class ScormElementManager(models.Manager):
    use_for_related_fields = True

    def get_queryset(self):
        return ScormElementQuerySet(self.model, using=self.db)

    def current(self,key):
        return self.get_queryset().current(key)

class ScormElement(models.Model):
    objects = ScormElementManager()

    attempt = models.ForeignKey(Attempt,on_delete=models.CASCADE,related_name='scormelements')
    key = models.CharField(max_length=200)
    value = models.TextField()
    time = models.DateTimeField(auto_now_add=True)
    current = models.BooleanField(default=True) # is this the latest version?

    class Meta:
        ordering = ['-time']

    def __str__(self):
        return '{}: {}'.format(self.key,self.value[:50]+(self.value[50:] and '...'))

#@receiver(models.signals.post_save,sender=ScormElement)
def set_current_scorm_element(sender,instance,created,**kwargs):
    ne = instance
    if created:
        for oe in ne.attempt.scormelements.current().filter(key=ne.key).exclude(pk=ne.pk):
            oe.current = False
            oe.save()

@receiver(models.signals.post_save,sender=ScormElement)
def scorm_set_score(sender,instance,created,**kwargs):
    if instance.key!='cmi.score.scaled' or not created:
        return

    instance.attempt.scaled_score = float(instance.value)
    instance.attempt.save()
    if instance.attempt.resource.report_mark_time == 'immediately':
        report_outcome_for_attempt(instance.attempt)

@receiver(models.signals.post_save,sender=ScormElement)
def scorm_set_completion_status(sender,instance,created,**kwargs):
    if instance.key!='cmi.completion_status' or not created:
        return

    instance.attempt.completion_status = instance.value
    instance.attempt.save()
    if instance.attempt.resource.report_mark_time == 'oncompletion' and instance.value=='completed':
        report_outcome_for_attempt(instance.attempt)
