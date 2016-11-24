from django.conf import settings
from django.db import models
from django.dispatch import receiver
from django.contrib.auth.models import User
import requests
from django.utils.text import slugify
from django.utils.translation import ugettext_lazy as _
from django.core import validators
from channels import Group
from django.utils import timezone

from .report_outcome import report_outcome,report_outcome_for_attempt

import os
import shutil
from zipfile import ZipFile
from lxml import etree
import re
import json
from collections import defaultdict

class NotDeletedManager(models.Manager):
    def get_queryset(self):
        return super(NotDeletedManager,self).get_queryset().filter(deleted=False)

class LTIConsumer(models.Model):
    key = models.CharField(max_length=100,unique=True,verbose_name=_('Consumer key'),help_text=_('The key should be human-readable, and uniquely identify this consumer.'))
    secret = models.CharField(max_length=100,verbose_name=_('Shared secret'))
    deleted = models.BooleanField(default=False)

    objects = NotDeletedManager()

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
    package = models.FileField(upload_to='exams/',verbose_name='Package file')

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
        re_objective_id_key = r'^cmi.objectives.([0-9]+).id$'
        top_key = ScormElement.objects.filter(attempt__resource=self,key__regex=re_objective_id_key).aggregate(models.Max('key'))['key__max']
        if top_key is None:
            return 0
        else:
            n = re.match(re_objective_id_key,top_key).group(1)
            return int(n)+1

    def user_data(self,user):
        return LTIUserData.objects.filter(resource=self,user=user).last()

    def part_hierarchy(self):
        """
            Returns an object
                {
                    question_num: {
                        part_num: {
                            gaps: [list of gap indices],
                            steps: [list of step indices]
                        }
                    }
                }
        """
        paths = sorted(set(e['value'] for e in ScormElement.objects.filter(attempt__resource=self,key__regex=r'cmi.interactions.\d+.id').values('value')),key=lambda x:(len(x),x))
        re_path = re.compile(r'q(\d+)p(\d+)(?:g(\d+)|s(\d+))?')
        out = defaultdict(lambda: defaultdict(lambda: {'gaps':[],'steps':[]}))
        for path in paths:
            m = re_path.match(path)
            if m is None:
                print(path)
            question_index = m.group(1)
            part_index = m.group(2)
            gap_index = m.group(3)
            step_index = m.group(4)
            p = out[question_index][part_index]
            if m.group(3):
                p['gaps'].append(step_index)
            elif m.group(4):
                p['steps'].append(gap_index)
    
        return out


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
    consumer = models.ForeignKey(LTIConsumer,on_delete=models.CASCADE,null=True)
    user = models.ForeignKey(User,on_delete=models.CASCADE,related_name='lti_data')
    resource = models.ForeignKey(Resource,on_delete=models.CASCADE)
    lis_result_sourcedid = models.CharField(max_length=200,default='',blank=True,null=True)
    lis_outcome_service_url = models.TextField(default='',blank=True,null=True)
    last_reported_score = models.FloatField(default=0)
    consumer_user_id = models.TextField(default='',blank=True,null=True)

class Attempt(models.Model):
    resource = models.ForeignKey(Resource,on_delete=models.CASCADE,related_name='attempts')
    exam = models.ForeignKey(Exam,on_delete=models.CASCADE,related_name='attempts')  # need to keep track of both resource and exam in case the exam later gets overwritten
    user = models.ForeignKey(User,on_delete=models.CASCADE,related_name='attempts')
    start_time = models.DateTimeField(auto_now_add=True)

    completion_status = models.CharField(max_length=20,choices=COMPLETION_STATUSES,default='not attempted')
    scaled_score = models.FloatField(default=0)

    deleted = models.BooleanField(default=False)
    broken = models.BooleanField(default=False)

    objects = NotDeletedManager()

    class Meta:
        ordering = ['-start_time',]

    def __str__(self):
        return 'Attempt by "{}" on "{}"'.format(self.user,self.resource)

    def get_element_default(self,key,default=None):
        try:
            return self.scormelements.current(key).value
        except ScormElement.DoesNotExist:
            return default

    def completed(self):
        return self.completion_status=='completed'

    @property
    def raw_score(self):
        if self.remarked_parts.exists() or self.resource.discounted_parts.exists():
            total = 0
            for i in range(self.resource.num_questions()):
                total += self.question_score(i)
            return total

        return float(self.get_element_default('cmi.score.raw',0))

    @property
    def max_score(self):
        if self.resource.discounted_parts.exists():
            total = 0
            for i in range(self.resource.num_questions()):
                total += self.question_max_score(i)
            return total

        return float(self.get_element_default('cmi.score.max',0))

    def part_discount(self,part):
        return self.resource.discounted_parts.filter(part=part).first()

    def part_paths(self):
        return self.scormelements.filter(key__regex='cmi.interactions.[0-9]+.id')

    def part_hierarchy(self):
        """
            Returns an object
                {
                    question_num: {
                        part_num: {
                            gaps: [list of gap indices],
                            steps: [list of step indices]
                        }
                    }
                }
        """
        paths = sorted(set(e['value'] for e in self.part_paths().values('value')),key=lambda x:(len(x),x))
        re_path = re.compile(r'q(\d+)p(\d+)(?:g(\d+)|s(\d+))?')
        out = defaultdict(lambda: defaultdict(lambda: {'gaps':[],'steps':[]}))
        for path in paths:
            m = re_path.match(path)
            if m is None:
                print(path)
            p = out[m.group(1)][m.group(2)]
            if m.group(3):
                p['gaps'].append(m.group(3))
            elif m.group(4):
                p['steps'].append(m.group(4))

        return out

    def part_gaps(self,part):
        if not re.match(r'q\d+p\d+$',part):
            return None
        gaps = self.part_paths().filter(value__startswith=part+'g')
        return set([g['value'] for g in gaps.values('value')])

    def part_interaction_id(self,part):
        id_element = self.part_paths().filter(value=part).get()
        n = re.match(r'cmi.interactions.(\d+).id',id_element.key).group(1)
        return n

    def part_score(self,part):
        discounted = self.part_discount(part)
        if discounted:
            return self.part_max_score(part)

        remarked = self.remarked_parts.filter(part=part)
        if remarked.exists():
            return remarked.get().score

        if self.remarked_parts.filter(part__startswith=part+'g').exists() or self.resource.discounted_parts.filter(part__startswith=part+'g').exists():
            gaps = self.part_gaps(part)
            return sum(self.part_score(g) for g in gaps)

        try:
            id = self.part_interaction_id(part)
        except ScormElement.DoesNotExist:
            return 0

        score = self.get_element_default('cmi.interactions.{}.result'.format(id),0)
        return float(score)

    def part_max_score(self,part):
        discounted = self.part_discount(part)
        if discounted:
            if discounted.behaviour == 'remove':
                return 0

        if DiscountPart.objects.filter(part__startswith=part+'g').exists():
            gaps = self.part_gaps(part)
            return sum(self.part_max_score(g) for g in gaps)

        try:
            id = self.part_interaction_id(part)
        except ScormElement.DoesNotExist:
            return 0

        return float(self.get_element_default('cmi.interactions.{}.weighting'.format(id),0))

    def question_score(self,n):
        qid = 'q{}'.format(n)
        if self.remarked_parts.filter(part__startswith=qid).exists() or self.resource.discounted_parts.filter(part__startswith=qid).exists():
            question_parts = self.part_paths().filter(value__startswith=qid)
            total = 0
            for p in question_parts:
                part = p.value
                if re.match(r'^q{}p\d+$'.format(n),part):
                    total += self.part_score(part)
            return total
        else:
            score = self.get_element_default('cmi.objectives.{}.score.raw'.format(n),0)
        return float(score)

    def question_max_score(self,n):
        qid = 'q{}'.format(n)
        if self.resource.discounted_parts.filter(part__startswith=qid).exists():
            question_parts = self.part_paths().filter(value__startswith=qid)
            total = 0
            for p in question_parts:
                part = p.value
                if re.match(r'^q{}p\d+$'.format(n),part):
                    total += self.part_max_score(part)
            return total
        else:
            score = self.get_element_default('cmi.objectives.{}.score.max'.format(n),0)
        return float(score)

    def channels_group(self):
        return 'attempt-{}'.format(self.pk)

class RemarkPart(models.Model):
    attempt = models.ForeignKey(Attempt,related_name='remarked_parts')
    part = models.CharField(max_length=20)
    score = models.FloatField()

DISCOUNT_BEHAVIOURS = [
    ('remove','Remove from total'),
    ('fullmarks','Award everyone full credit'),
]

class DiscountPart(models.Model):
    resource = models.ForeignKey(Resource,related_name='discounted_parts')
    part = models.CharField(max_length=20)
    behaviour = models.CharField(max_length=10,choices=DISCOUNT_BEHAVIOURS,default='remove')

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

@receiver(models.signals.post_save,sender=ScormElement)
def send_scorm_element_to_dashboard(sender,instance,created,**kwargs):
    Group(instance.attempt.channels_group()).send({
        "text": json.dumps({
            'key': instance.key,
            'value': instance.value,
            'time': instance.time.strftime('%Y-%m-%d %H:%M:%S'),
        })
    })

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

class EditorLink(models.Model):
    url = models.URLField(verbose_name='Base URL of the editor')
    projects = models.CharField(max_length=200,default='',verbose_name='IDs of projects to scan for exams',validators=[validators.validate_comma_separated_integer_list])
    cached_available_exams = models.TextField(blank=True,editable=False,verbose_name='Cached JSON list of available exams from this editor')
    last_cache_update = models.DateTimeField(blank=True,editable=False,verbose_name='Time of last cache update')

    def update_cache(self):
        r = requests.get('{}/api/available-exams'.format(self.url))
        self.cached_available_exams = r.text
        self.last_cache_update = timezone.now()

    @property
    def available_exams(self):
        if self.cached_available_exams:
            return json.loads(self.cached_available_exams)
        else:
            return []

@receiver(models.signals.pre_save,sender=EditorLink)
def update_editor_cache_before_save(sender,instance,**kwargs):
    instance.update_cache()
