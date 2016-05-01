from django.conf import settings
from django.db import models
from django.dispatch import receiver
from django.contrib.auth.models import User

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


class Resource(models.Model):
    resource_link_id = models.CharField(max_length=300)
    tool_consumer_instance_guid = models.CharField(max_length=300)
    exam = models.ForeignKey(Exam,blank=True,null=True,on_delete=models.SET_NULL)

    def __str__(self):
        return '{} {}'.format(self.tool_consumer_instance_guid,self.resource_link_id)

class Attempt(models.Model):
    resource = models.ForeignKey(Resource)
    exam = models.ForeignKey(Exam)  # need to keep track of both resource and exam in case the exam later gets overwritten
    user = models.ForeignKey(User)
    start_time = models.DateTimeField(auto_now_add=True)

class ScormElement(models.Model):
    attempt = models.ForeignKey(Attempt)
    key = models.CharField(max_length=200)
    value = models.TextField()
    time = models.DateTimeField(auto_now_add=True)
    current = models.BooleanField(default=True) # is this the latest version?

@receiver(models.signals.post_save,sender=ScormElement)
def set_current_scorm_element(sender,instance,created,**kwargs):
    ne = instance
    if created:
        for oe in ScormElement.objects.filter(attempt=ne.attempt, key=ne.key, current=True).exclude(pk=ne.pk):
            oe.current = False
            oe.save()
