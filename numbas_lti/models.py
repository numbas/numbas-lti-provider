from django.conf import settings
from django.db import models
from django.dispatch import receiver
from django.contrib.auth.models import User
import requests

from .report_outcome import report_outcome

import os
import shutil
from zipfile import ZipFile
from lxml import etree

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
    ('highest','Highest score'),
    ('last','Last attempt'),
]

class Resource(models.Model):
    resource_link_id = models.CharField(max_length=300)
    tool_consumer_instance_guid = models.CharField(max_length=300)
    exam = models.ForeignKey(Exam,blank=True,null=True,on_delete=models.SET_NULL)

    grading_method = models.CharField(max_length=20,choices=GRADING_METHODS,default='highest',verbose_name='Grading method')
    include_incomplete_attempts = models.BooleanField(default=True,verbose_name='Include incomplete attempts in grading')

    max_attempts = models.PositiveIntegerField(default=0,verbose_name='Maximum attempts per user')

    def __str__(self):
        if self.exam:
            return str(self.exam)
        else:
            return '{} {} - no exam uploaded'.format(self.tool_consumer_instance_guid,self.resource_link_id)

    def grade_user(self,user):
        methods = {
            'highest': self.grade_highest,
            'last': self.grade_last,
        }
        attempts = self.attempts.filter(user=user)
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

COMPLETION_STATUSES = [
    ('not attempted','Not attempted'),
    ('incomplete','Incomplete'),
    ('completed','Complete'),
]

class AccessToken(models.Model):
    user = models.ForeignKey(User,on_delete=models.CASCADE,related_name='access_tokens')
    resource = models.ForeignKey(Resource,on_delete=models.CASCADE,related_name='access_tokens')

class LTIUserData(models.Model):
    user = models.ForeignKey(User,on_delete=models.CASCADE,related_name='lti_data')
    resource = models.ForeignKey(Resource,on_delete=models.CASCADE)
    lis_result_sourcedid = models.CharField(max_length=200,default='')
    lis_outcome_service_url = models.TextField(default='')

class Attempt(models.Model):
    resource = models.ForeignKey(Resource,on_delete=models.CASCADE,related_name='attempts')
    exam = models.ForeignKey(Exam,on_delete=models.CASCADE,related_name='attempts')  # need to keep track of both resource and exam in case the exam later gets overwritten
    user = models.ForeignKey(User,on_delete=models.CASCADE,related_name='attempts')
    start_time = models.DateTimeField(auto_now_add=True)

    completion_status = models.CharField(max_length=20,choices=COMPLETION_STATUSES,default='not attempted')
    scaled_score = models.FloatField(default=0)

    class Meta:
        ordering = ['-start_time',]

    @property
    def raw_score(self):
        try:
            return float(self.scormelements.current('cmi.score.raw').value)
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
            print("not current",oe.pk,ne.pk)
            oe.current = False
            oe.save()

@receiver(models.signals.post_save,sender=ScormElement)
def scorm_set_score(sender,instance,created,**kwargs):
    if instance.key!='cmi.score.scaled' or not created:
        return

    instance.attempt.scaled_score = float(instance.value)
    instance.attempt.save()
    report_outcome(instance.attempt)

@receiver(models.signals.post_save,sender=ScormElement)
def scorm_set_completion_status(sender,instance,created,**kwargs):
    if instance.key!='cmi.completion_status' or not created:
        return

    instance.attempt.completion_status = instance.value
    instance.attempt.save()
    report_outcome(instance.attempt)
