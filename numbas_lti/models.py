from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from collections import defaultdict
from dataclasses import dataclass
from django.conf import settings
from django.contrib.auth.models import User
from django.core import signing
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.base import ContentFile
from django.core.mail import send_mail
from django.db import models, transaction
from django.db.utils import OperationalError
from django.db.models import Min, Count, Q, Subquery, OuterRef, Func, F
from django.template.loader import get_template
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _, gettext, ngettext
from django.core import validators
from django.utils import timezone
from datetime import timedelta,datetime
from django_auth_lti.patch_reverse import reverse
import json
from lxml import etree
import os
from pathlib import Path
from pylti1p3.assignments_grades import AssignmentsGradesService, LineItem
from pylti1p3.names_roles import NamesRolesProvisioningService
from pylti1p3.contrib.django.lti1p3_tool_config import DjangoDbToolConf
from pylti1p3.contrib.django.lti1p3_tool_config.models import LtiTool, LtiToolKey
from pylti1p3.dynamic_registration import generate_key_pair
from pylti1p3.exception import LtiException
from pylti1p3.lineitem import LineItem
import pylti1p3.roles
from pylti1p3.contrib.django.service_connector import DjangoServiceConnector
import re
import shutil
import time
from typing import Optional
import uuid
from zipfile import ZipFile

from . import requests_session
from .exceptions import LineItemDoesNotExist
from .groups import group_for_attempt, group_for_resource_stats, group_for_resource
from .diff import make_diff, apply_diff
from .util import parse_scorm_timeinterval, iso_time, time_from_iso
from .examparser import numbasobject

requests = requests_session.get_session()

class NotDeletedManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(deleted=False)

    def deleted(self):
        return super().get_queryset().filter(deleted=True)

IDENTIFIER_FIELDS = [
    ('username', _('Username')),
    ('email', _('Email address')),
    ('', _('None')),
]

class LTIConsumer(models.Model):
    """
        An LTI consumer.
        Specific settings for the LTI 1.1 and LTI 1.3 protocols are in separate models, ``LTI_11_Consumer`` and ``LTI_13_Consumer``.
    """
    url = models.URLField(blank=True,default='',verbose_name=_('Home URL of consumer'))
    deleted = models.BooleanField(default=False)
    identifier_field = models.CharField(default='', blank=True, max_length=20, choices=IDENTIFIER_FIELDS, verbose_name=_('Field used to identify students'))

    objects = NotDeletedManager()

    class Meta:
        verbose_name = _('LTI consumer')
        verbose_name_plural = _('LTI consumers')

    def __str__(self):
        return f'Consumer "{self.title}" (ID: {self.pk})'

    def get_absolute_url(self):
        return reverse('view_consumer', args=(self.pk,))

    @property
    def title(self):
        if hasattr(self, 'lti_11'):
            return self.lti_11.key
        elif hasattr(self, 'lti_13'):
            return self.lti_13.tool.title

    @property
    def resources(self):
        return Resource.objects.filter(Q(lti_11_links__context__consumer=self) | Q(lti_13_links__context__consumer=self))

    def contexts_grouped_by_period(self):
        resources = Resource.objects.filter(Q(lti_13_links__context=OuterRef('pk')) | Q(lti_11_links__context=OuterRef('pk')))
        contexts = self.contexts.exclude(name='').annotate(
            creation=Subquery(resources.order_by('creation_time').values('creation_time')[:1]),
            num_attempts= \
                Count('lti_11_resource_links__resource__attempts', filter=Q(lti_11_resource_links__resource__attempts__broken=False), distinct=True) + \
                Count('lti_13_resource_links__resource__attempts', filter=Q(lti_13_resource_links__resource__attempts__broken=False), distinct=True)
        ).order_by('-creation')

        if not self.time_periods.exists():
            return [(None,contexts)]
        it = iter(self.time_periods.order_by('-end'))
        p = next(it)
        out = []
        lafter = []
        lduring = []
        for c in contexts.exclude(creation=None):
            while p is not None and c.creation<p.start:
                if len(lafter):
                    out.append((None,lafter))
                if len(lduring):
                    out.append((p,lduring))
                lafter = []
                lduring = []
                try:
                    p = next(it)
                except StopIteration:
                    p = None
            if p is None:
                lafter.append(c)
                continue
            if c.creation>p.end:
                lafter.append(c)
            else:
                lduring.append(c)
        if len(lafter):
            out.append((None,lafter))
        if len(lduring):
            out.append((p,lduring))
        no_creation = contexts.filter(creation=None)
        if no_creation.exists():
            out.append((None,no_creation[:]))
        groups = [(p,sorted(cs,key=lambda c:c.name.upper())) for p,cs in out]
        return groups

class LTIConsumerRegistrationToken(models.Model):
    """ 
        A token allowing one registration of an LTI consumer by dynamic registration.
    """
    uid = models.UUIDField(default = uuid.uuid4, primary_key = True)
    created = models.DateTimeField(auto_now_add = True)
    name = models.CharField(max_length=500, verbose_name=_('Intended use for this token'))

    class Meta:
        verbose_name = _('LTI consumer registration token')
        verbose_name_plural = _('LTI consumer registration tokens')

    def __str__(self):
        return f'{self.uid} ({self.name})'

    def get_absolute_url(self):
        return reverse('lti_13:view_dynamic_registration_token', kwargs={'pk':self.uid})


def register_lti_13_tool(issuer, key_set_url, auth_login_url, title, client_id, deployment_ids, **kwargs) -> LTIConsumer:
    private_key, public_key = generate_key_pair()

    key, created_key = LtiToolKey.objects.get_or_create(name=issuer, defaults = {'private_key': private_key, 'public_key': public_key})

    tool = LtiTool.objects.create(
        title=title,
        issuer=issuer,
        auth_login_url=auth_login_url,
        key_set_url=key_set_url,
        tool_key=key,
        client_id=client_id,
        deployment_ids = deployment_ids
    )

    return tool

class LTI_11_Consumer(models.Model):
    consumer = models.OneToOneField(LTIConsumer, related_name='lti_11', on_delete=models.CASCADE)
    key = models.CharField(max_length=100,unique=True,verbose_name=_('Consumer key'),help_text=_('The key should be human-readable, and uniquely identify this consumer.'))
    secret = models.CharField(max_length=100,verbose_name=_('Shared secret'))

class LTI_11_UserAlias(models.Model):
    consumer = models.ForeignKey(LTIConsumer, related_name='lti_11_user_aliases', on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name='lti_11_aliases', on_delete=models.CASCADE)
    consumer_user_id = models.TextField(blank=True, null=True)

class LTI_13_Consumer(models.Model):
    consumer = models.OneToOneField(LTIConsumer, related_name='lti_13', on_delete=models.CASCADE)
    tool = models.OneToOneField(LtiTool, related_name='numbas', on_delete=models.CASCADE)

class LTI_13_UserAlias(models.Model):
    consumer = models.ForeignKey(LTIConsumer, related_name='lti_13_user_aliases', on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name='lti_13_aliases', on_delete=models.CASCADE)
    sub = models.CharField(max_length=255) # The platform's identifier for the user
    lis_person_sourcedid = models.CharField(max_length=255, blank=True, null=True) # Another identifier for the user from the platform.

    full_name = models.CharField(max_length=1000, blank=True, default='')
    given_name = models.CharField(max_length=1000, blank=True, default='')
    family_name = models.CharField(max_length=1000, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    locale = models.CharField(max_length=30, blank=True, default='')

class ConsumerTimePeriod(models.Model):
    consumer = models.ForeignKey(LTIConsumer, related_name='time_periods', on_delete=models.CASCADE)
    start = models.DateTimeField()
    end = models.DateTimeField()
    name = models.CharField(max_length=300)

    class Meta:
        verbose_name = _('time period')
        verbose_name_plural = _('time periods')
        ordering = ['-end','-start']

class ExtractPackage(models.Model):
    extract_folder = 'extracted_zips'
    static_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name=_('UUID of exam package on disk'))

    class Meta:
        abstract = True

    @property
    def extracted_path(self):
        return os.path.join(os.getcwd(), settings.MEDIA_ROOT,self.extract_folder,self.__class__.__name__,str(self.static_uuid))

    @property
    def extracted_url(self):
        return '{}{}/{}/{}'.format(settings.MEDIA_URL,self.extract_folder,self.__class__.__name__,str(self.static_uuid))

# Create your models here.
class Exam(ExtractPackage):
    title = models.CharField(max_length=300)
    package = models.FileField(upload_to='exams/',verbose_name=_('Package file'))
    retrieve_url = models.URLField(blank=True,default='',verbose_name=_('URL used to retrieve the exam package'))
    rest_url = models.URLField(blank=True,default='',verbose_name=_('URL of the exam on the editor\'s REST API'))
    creation_time = models.DateTimeField(auto_now_add=True, verbose_name=_('Time this exam was created'))
    resource = models.ForeignKey('Resource',null=True,blank=True,on_delete=models.SET_NULL,related_name='exams')

    class Meta:
        verbose_name = _('exam')
        verbose_name_plural = _('exams')
        ordering = ['-creation_time','title']

    def __str__(self):
        return self.title

    def is_active(self):
        return self.resource is not None and self==self.resource.exam

    def manifest(self):
        root = Path(self.extracted_path)
        manifest_path = root / 'numbas-manifest.json'
        if not manifest_path.exists():
            return {}

        try:
            with open(str(manifest_path)) as f:
                manifest = json.loads(f.read())
                return manifest
        except Exception as e:
            return {}

    def supports_feature(self, feature):
        features = self.manifest().get('features',{})
        return features.get(feature)

    def source(self):
        try:
            with open(str(Path(self.extracted_path) / 'source.exam')) as f:
                content = f.read()
                obj = numbasobject.NumbasObject(source=content)
                return obj.data
        except (FileNotFoundError,json.JSONDecodeError, numbasobject.VersionError):
            return {}

    def has_duration(self):
        source = self.source()
        if self.source is None:
            return True
        duration = source.get('duration',0)
        return duration != 0

    @property
    def duration(self):
        if not hasattr(self,'_duration'):
            source = self.source()
            if source is not None:
                duration = source.get('duration',0) / 60
                self._duration = duration
            else:
                self._duration = 0

        return self._duration

    def get_feedback_settings(self, completed, review_allowed):
        content = self.source()

        def get(node, attr, default=None):
            return node.get(attr, node.get(attr.lower(), default))

        feedback = get(content, 'feedback', {})

        def resolve_feedback_setting(setting):
            return {
                'always': True,
                'oncompletion': completed,
                'inreview': review_allowed,
                'never': False,
            }[setting]

        info = [
            (_('Maximum available score'),  get(feedback,'showTotalMarkWhen', 'always')),
            (_('Whether answers are correct'),  get(feedback,'showAnswerStateWhen', 'always')),
            (_('Awarded scores'),  get(feedback,'showActualMarkWhen', 'always')),
            (_('Feedback messages for each question part'), get(feedback, 'showPartFeedbackMessagesWhen', 'always')),
            (_('Expected answers to each part'), get(feedback, 'showExpectedAnswersWhen', 'inreview')),
            (_('Advice for each question'), get(feedback, 'showAdviceWhen', 'inreview')),
        ]

        return info

    def part_hierarchy(self):
        data = self.source()

        hierarchy = {}
        qn = 0
        for qg in data.get('question_groups',[]):
            for q in qg.get('questions',[]):
                qd = hierarchy[qn] = {}
                for i,part in enumerate(q.get('parts',[])):
                    p = {'gaps': [], 'steps': []}
                    if part['type'] == 'gapfill':
                        p['gaps'] = list(range(len(part.get('gaps',[]))))
                    p['steps'] = list(range(len(part.get('steps',[]))))
                    qd[i] = p
                qn += 1
        
        return hierarchy


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

SHOW_SCORES_MODES = [
    ('always',_('Always')),
    ('complete',_('When attempt is complete')),
    ('review', _('When review is allowed')),
    ('never',_('Never')),
]

class LTIContext(models.Model):
    consumer = models.ForeignKey(LTIConsumer,related_name='contexts', on_delete=models.CASCADE)
    context_id = models.CharField(max_length=300)
    name = models.CharField(max_length=300)
    label = models.CharField(max_length=300)
    instance_guid = models.CharField(max_length=300)

    class Meta:
        verbose_name = _('LTI context')
        verbose_name_plural = _('LTI contexts')
        unique_together = (('context_id', 'instance_guid', 'consumer'),)

    def __str__(self):
        if self.name == self.label:
            return self.name
        else:
            return '{} ({})'.format(self.name, self.label)

    @property
    def resources(self):
        return Resource.objects.filter(Q(lti_11_links__context=self) | Q(lti_13_links__context=self))

    def get_absolute_url(self):
        return reverse('view_context', args=(self.pk,))

class LTI_13_Context(models.Model):
    tool_conf = DjangoDbToolConf()

    context = models.OneToOneField(LTIContext, on_delete=models.CASCADE, related_name='lti_13')
    ags_data = models.JSONField(blank=True, default=dict, null=True)
    nrps_data = models.JSONField(blank=True, default=dict, null=True)

    cached_lineitems = models.JSONField(blank=True, default=dict, null=True)
    lineitems_last_fetched = models.DateTimeField(blank=True, null=True, verbose_name=_('Last time line AGS items fetched'))

    def get_service_connector(self):
        tool = self.context.consumer.lti_13.tool

        registration = self.tool_conf.find_registration_by_params(iss=tool.issuer, client_id=tool.client_id)

        service_connector = DjangoServiceConnector(registration, requests_session.get_session())
    
        return service_connector

    def get_ags(self):
        """
            Get the Assignments and Grades Service controller for this context.
        """
        if self.ags_data:
            return AssignmentsGradesService(self.get_service_connector(), self.ags_data)

    def get_nrps(self):
        """
            Get the Names and Roles Provisioning Service controller for this context.
        """

        if self.nrps_data:
            return NamesRolesProvisioningService(self.get_service_connector(), self.nrps_data)

    def nrps_members(self):
        cache_key = f'nrps_members-{self.pk}'

        members = cache.get(cache_key)
        if members is not None:
            return members

        try:
            nrps = self.get_nrps()
            raw_members = nrps.get_members()
        except LtiException:
            return []

        members = [
            {
                'name': m.get('name'),
                'given_name': m.get('given_name'),
                'family_name': m.get('family_name'),
                'active': m.get('status') == 'Active',
                'student': pylti1p3.roles.StudentRole({"https://purl.imsglobal.org/spec/lti/claim/roles": m['roles']}).check(),
                'user_id': m['user_id'],
                'ext_user_username': m.get('ext_user_username'),
                'email': m.get('email'),
            }
            for m in sorted(raw_members, key=lambda x: (x.get('family_name',''), x.get('given_name',''), x.get('user_id')))
        ]
        cache.set(cache_key, members, 60)

        return members

    def ags_lineitems(self, force_fetch=False):
        if force_fetch or not self.cached_lineitems:
            ags = self.get_ags()
            lineitems = list(ags.get_lineitems())
            self.cached_lineitems = lineitems
            self.lineitems_last_fetched = timezone.now()
            self.save(update_fields=['cached_lineitems', 'lineitems_last_fetched'])

        return self.cached_lineitems

REQUIRE_LOCKDOWN_APP_CHOICES = [
    ('', _('No')),
    ('numbas', _('Numbas lockdown app')),
    ('seb', _('Safe Exam Browser')),
]

class SebSettings(models.Model):
    name = models.CharField(max_length=200, verbose_name=_('Name'), help_text=_('A descriptive name for this settings file.'))
    settings_file = models.FileField(upload_to='seb_settings/', verbose_name=_('Settings file'), help_text=_('Save the settings file and upload it here.'))
    config_key_hash = models.CharField(max_length=64, verbose_name=_('Configuration key'), help_text=_('Turn on <strong>Use Browser Exam Key and Configuration Key</strong>, and paste the Configuration Key in the tool here.'))
    password = models.CharField(max_length=30, blank=True, verbose_name=_('Password'), help_text=_('If you set a <strong>Settings password</strong> and would like the Numbas LTI tool to show it to the student, paste it here.'))

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('edit_seb_settings',args=(self.pk,))

LINEITEM_CHOICES = [
    ('no', _('No')),
    ('yes', _('Yes')),
    ('unwanted', _('Not wanted')),
]

@dataclass
class Availability:
    """
        A representation of the times when a resource is available.
    """
    from_time: Optional[datetime]
    until_time: Optional[datetime]
    due_date: Optional[datetime]

class Resource(models.Model):
    exam = models.ForeignKey(Exam,blank=True,null=True,on_delete=models.SET_NULL,related_name='main_exam_of')
    title = models.CharField(max_length=300,default='')
    description = models.TextField(default='')

    creation_time = models.DateTimeField(auto_now_add=True, verbose_name=_('Time this resource was created'))

    grading_method = models.CharField(max_length=20,choices=GRADING_METHODS,default='highest',verbose_name=_('Grading method'))
    include_incomplete_attempts = models.BooleanField(default=True,verbose_name=_('Include incomplete attempts in grading?'))
    show_marks_when = models.CharField(max_length=20, default='always', choices=SHOW_SCORES_MODES, verbose_name=_('When to show scores to students'))
    available_from = models.DateTimeField(blank=True, null=True, verbose_name=_('Available from'), help_text=_('Before this time, students may not start or resume attempts.'))
    available_until = models.DateTimeField(blank=True, null=True, verbose_name=_('Available until'), help_text=_('Attempts will end automatically at this time and students may not resume or start new attempts. Students may review existing attempts after this time.'))
    due_date = models.DateTimeField(blank=True, null=True, verbose_name=_('Due date'), help_text=_('At this time, any open attempts will automatically end. Students may review existing attempts or re-open them while the resource is available.'))
    allow_review_from = models.DateTimeField(blank=True, null=True, verbose_name=_('Allow students to review attempts from'))
    allow_student_reopen = models.BooleanField(default=False, verbose_name=_('Allow students to re-open attempts while the resource is available?'))
    report_mark_time = models.CharField(max_length=20,choices=REPORT_TIMES,default='immediately',verbose_name=_('When to report scores back'))
    email_receipts = models.BooleanField(default=False,verbose_name=_('Email attempt receipts to students on completion?'))

    max_attempts = models.PositiveIntegerField(default=0,verbose_name=_('Maximum attempts per user'), help_text=_('Zero means unlimited attempts.'))

    num_questions = models.PositiveIntegerField(default=0)

    require_lockdown_app = models.CharField(max_length=20, default='', blank=True, choices = REQUIRE_LOCKDOWN_APP_CHOICES, verbose_name=_("Require a lockdown app?"))

    lockdown_app_password = models.CharField(max_length=30, blank=True, verbose_name=_('Password for the Numbas lockdown app'))
    show_lockdown_app_password = models.BooleanField(default=False, verbose_name=_('Show the password for the lockdown app on the launch page?'))

    seb_settings = models.ForeignKey(SebSettings, blank=True, null=True, on_delete=models.SET_NULL, related_name='resources')

    lineitem_unwanted = models.BooleanField(default=False, verbose_name=_('Grades service line item unwanted?'))

    class Meta:
        verbose_name = _('resource')
        verbose_name_plural = _('resources')
        ordering = ['-creation_time','title']

    def __str__(self):
        if self.exam:
            return "Resource {}: {}".format(self.pk, self.exam)
        elif self.lti_11_links.exists():
            link = self.lti_11_links.first()
            return _('Resource linked to "{context}"').format(context=link.context)
        elif self.lti_13_links.exists():
            link = self.lti_13_links.first()
            return _('Resource linked to "{context}"').format(context=link.context)
        else:
            return gettext('Resource with no context')

    @property
    def slug(self):
        if self.exam:
            return slugify(self.exam.title)
        else:
            return 'resource'

    def lti_contexts(self):
        """
            LTI Contexts that this resource is linked to.
        """

        return LTIContext.objects.filter(Q(lti_11_resource_links__resource=self) | Q(lti_13_resource_links__resource=self)).distinct()

    def lti_13_contexts(self):
        return LTI_13_Context.objects.filter(context__lti_13_resource_links__resource=self).distinct()

    def lti_11_contexts(self):
        return LTIContext.objects.filter(lti_11_resource_links__resource=self)

    def unbroken_attempts(self):
        return self.attempts.filter(broken=False)

    def grade_user(self,user):
        """
            Find the attempt representing the user's grade at this resource.
            Depends on ``grading_method``.
        """
        
        methods = {
            'highest': '-scaled_score',
            'last': '-start_time',
        }

        
        attempts = self.attempts.filter(user=user)
        if not self.include_incomplete_attempts:
            attempts = attempts.filter(completion_status='completed')
        if not attempts.exists():
            return None

        attempt = attempts.order_by(methods[self.grading_method]).first()

        completion_status = 'completed' if attempt.completed() else attempt.completion_status

        submitted_at = attempt.get_end_time()

        return attempt, completion_status, submitted_at

    def students(self):
        return User.objects.filter(attempts__resource=self, attempts__deleted=False).distinct().order_by('last_name','first_name')

    def available_for_user(self,user=None):
        afrom = self.available_from
        auntil = self.available_until
        due_date = self.due_date

        deadline_extension = timedelta(0)
        if user is not None:
            changes = self.access_changes.for_user(user)
            for change in changes:
                if change.extend_deadline is not None:
                    deadline_extension = change.extend_deadline

                if change.available_from is not None:
                    afrom = change.available_from
                if change.available_until is not None:
                    auntil = change.available_until
                if change.due_date is not None:
                    due_date = change.due_date

        if due_date is not None:
            due_date += deadline_extension

        return Availability(from_time=afrom, until_time=auntil, due_date=due_date)

    def duration_extension_for_user(self, user):
        duration = 0

        if self.exam is not None:
            duration = self.exam.duration

        best_minutes = 0
        best_extension = (None,None)

        for ac in self.access_changes.for_user(user).exclude(extend_duration=None):
            extension_minutes = ac.extend_duration_absolute(duration)
            if extension_minutes > best_minutes:
                best_minutes = extension_minutes
                best_extension = (ac.extend_duration, ac.extend_duration_units)

        return best_extension

    def duration_disabled_for_user(self, user):
        return self.access_changes.for_user(user).filter(disable_duration=True).exists()

    def availability_json(self,user=None):
        availability = self.available_for_user(user)

        if user is not None:
            extension_amount, extension_units = self.duration_extension_for_user(user)
        else:
            extension_amount, extension_units = None, None
        data = {
            'available_from': iso_time(availability.from_time),
            'available_until': iso_time(availability.until_time),
            'due_date': iso_time(availability.due_date),
            'allow_review_from': iso_time(self.allow_review_from),
            'duration_extension': {
                'amount': extension_amount,
                'units': extension_units,
            },
            'disable_duration': self.duration_disabled_for_user(user)
        }
        return data

    def is_available(self,user=None):
        if user is not None and user.is_anonymous:
            return False

        availability = self.available_for_user(user)

        if availability.from_time is None and availability.until_time is None:
            return True

        now = timezone.now()

        available = False
        if availability.from_time is None or availability.until_time is None:
            available = (availability.from_time is None or now >= availability.from_time) and (availability.until_time is None or now<=availability.until_time)
        elif availability.from_time < availability.until_time:
            available = availability.from_time <= now <= availability.until_time
        else:
            available = now <= availability.until_time or now >= availability.from_time

        return available


    def send_access_changes(self):
        channel_layer = get_channel_layer()
        group_send = async_to_sync(channel_layer.group_send)

        group = group_for_resource(self)
        group_send(group,{'type': 'availability.changed'})

    def max_attempts_for_user(self,user):
        max_attempts = self.max_attempts
        if max_attempts>0:
            for ac in self.access_changes.for_user(user).exclude(max_attempts=None):
                if ac.max_attempts == 0:
                    max_attempts = 0
                    break
                else:
                    max_attempts = max(max_attempts,ac.max_attempts)
        return max_attempts

    def can_start_new_attempt(self,user):
        if not self.is_available(user):
            return False

        max_attempts = self.max_attempts_for_user(user)

        if max_attempts==0:
            return True

        return self.attempts.filter(user=user).exclude(broken=True).count()<max_attempts or AccessToken.objects.filter(resource=self,user=user).exists()

    def user_data(self,user):
        if user.is_anonymous:
            return None
        return LTIUserData.objects.filter(resource=self,user=user).last()

    def part_hierarchy(self):
        if self.exam is None:
            return {}
        return self.exam.part_hierarchy()

    def last_activity(self):
        if self.attempts.exists():
            return self.attempts.order_by('-start_time').first().start_time
        else:
            return self.creation_time

    def time_since_last_activity(self):
        now = timezone.now()
        diff = now - self.last_activity()
        return diff

    def is_new(self):
        return self.time_since_last_activity().days < 7

    def is_old(self):
        return self.time_since_last_activity().days > 14

    def live_stats_data(self):
        question_data = [
            {
                'number': s.number, 
                'raw_score': s.raw_score, 
                'scaled_score': s.scaled_score, 
                'max_score': s.max_score, 
                'completion_status': s.completion_status,
            } 
            for s in AttemptQuestionScore.objects.filter(attempt__resource=self)
        ]
        attempt_data = [
            {
                'scaled_score': a.scaled_score,
                'completion_status': a.completion_status,
                'start_time': a.start_time.isoformat(),
                'end_time': a.end_time.isoformat() if a.end_time is not None else None,
                'time_spent': a.time_spent().total_seconds()*1000
            }
            for a in self.attempts.all()
        ]
        data = {
            'questions': question_data,
            'attempts': attempt_data,
        }
        return data

    def receipt_salt(self):
        return 'numbas_lti:resource:'+str(self.pk)

    def task_report_scores(self):
        from . import tasks
        tasks.resource_report_scores(self)

    def require_lockdown_app_for_user(self, user=None):
        require_lockdown_app = self.require_lockdown_app
        seb_settings = self.seb_settings
        lockdown_app_password = self.lockdown_app_password
        if user is not None:
            change = self.access_changes.for_user(user).exclude(require_lockdown_app='unchanged').last()
            if change is not None:
                require_lockdown_app = change.require_lockdown_app
                seb_settings = change.seb_settings
                if require_lockdown_app == 'numbas':
                    if change.lockdown_app_password:
                        lockdown_app_password = change.lockdown_app_password
                elif require_lockdown_app == 'seb':
                    lockdown_app_password = change.seb_settings.password

        if require_lockdown_app == 'numbas':
            if not lockdown_app_password:
                lockdown_app_password = settings.LOCKDOWN_APP.get('password')
        
        if require_lockdown_app == 'seb':
            try:
                lockdown_app_password = seb_settings.password
            except (SebSettings.DoesNotExist, AttributeError):
                lockdown_app_password = None

        return (require_lockdown_app, lockdown_app_password, seb_settings)

    def get_lockdown_app_password(self, user=None):
        _, lockdown_app_password, _ = self.require_lockdown_app_for_user(user)
        return lockdown_app_password

    def estimate_max_score(self):
        """
            Estimate the maximum score for this resource.
            Because the maximum score for a question can't be determined without running it, and might be different for different attempts, we can only estimate the maximum score by looking at an attempt at the exam.
            If no attempts exist, return 1.
            LTI platforms only store the scaled score, so this can only help readability and shouldn't affect any automated decisions.
        """
        try:
            attempt = self.attempts.first()
            if attempt is None:
                return 1
            return attempt.max_score
        except Attempt.DoesNotExist:
            return 1

    def get_lti_13_lineitem(self, create = False):
        lineitem_dict = {
            "scoreMaximum": self.estimate_max_score(),
            "tag": "grade",
            "label": self.title,
            "resourceId": f"resource-{self.pk}",
        }
        lineitem = LineItem(lineitem_dict)

        if self.available_from is not None:
            lineitem.set_start_date_time(self.available_from.isoformat())
        if self.due_date is not None:
            lineitem.set_end_date_time(self.due_date.isoformat())

        resource_link_ids = self.lti_13_links.values_list('resource_link_id', flat=True)

        condition = lambda l: l.get('resourceLinkId') in resource_link_ids or (l.get('tag')==lineitem.get_tag() and l.get('resourceId')==lineitem.get_resource_id())

        lti_13_context = self.lti_13_contexts().first()
        lineitems = lti_13_context.ags_lineitems(force_fetch=create)
        ags = lti_13_context.get_ags()

        try:
            saved_lineitem = next(l for l in lineitems if condition(l))
        except StopIteration:
            if create:
                saved_lineitem = ags.create_lineitem(lineitem)
                lti_13_context.ags_lineitems(force_fetch=True)
            else:
                raise LineItemDoesNotExist(self)

        saved_lineitem = LineItem(saved_lineitem)

        if (saved_lineitem.get_score_maximum() != lineitem.get_score_maximum()
            or time_from_iso(saved_lineitem.get_start_date_time()) != time_from_iso(lineitem.get_start_date_time())
            or time_from_iso(saved_lineitem.get_end_date_time()) != time_from_iso(lineitem.get_end_date_time())
            or saved_lineitem.get_tag() != lineitem.get_tag()
            ):
            max_score = lineitem.get_score_maximum()

            if max_score is not None and max_score > 0:
                saved_lineitem.set_score_maximum(max_score)
            saved_lineitem.set_start_date_time(lineitem.get_start_date_time())
            saved_lineitem.set_end_date_time(lineitem.get_end_date_time())
            saved_lineitem.set_tag(lineitem.get_tag())
            self.update_lti_13_lineitem(ags, saved_lineitem)

        return saved_lineitem

    def update_lti_13_lineitem(self, ags, lineitem=None):
        """
            Update the AGS line item for this resource on the platform.

            If ``lineitem`` isn't given, the default line item is created by ``get_lti_13_lineitem``.
        """

        if lineitem is None:
            lineitem = self.get_lti_13_lineitem()

        scope = ags._service_data['scope']

        access_token = ags._service_connector.get_access_token(scope)

        url = lineitem.get_id()
        if url is None:
            raise Exception("The line item does not have an ID.")

        ags._service_connector._requests_session.put(
            lineitem.get_id(),
            data=lineitem.get_value(),
            headers={
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json',
                'Content-Type': 'application/vnd.ims.lis.v2.lineitem+json'
            }
        )

        return lineitem


class LTI_11_ResourceLink(models.Model):
    resource = models.ForeignKey(Resource, related_name='lti_11_links', on_delete=models.CASCADE)
    resource_link_id = models.CharField(max_length=300)
    context = models.ForeignKey(LTIContext,blank=True,null=True,on_delete=models.SET_NULL,related_name='lti_11_resource_links')

class LTI_13_ResourceLink(models.Model):
    resource = models.ForeignKey(Resource, related_name='lti_13_links', on_delete=models.CASCADE)
    resource_link_id = models.CharField(max_length=300)
    title = models.CharField(max_length=300,default='')
    description = models.TextField(default='', blank=True)
    context = models.ForeignKey(LTIContext,blank=True,null=True,on_delete=models.SET_NULL,related_name='lti_13_resource_links')

class ReportProcess(models.Model):
    resource = models.ForeignKey(Resource,on_delete=models.CASCADE,related_name='report_processes')
    status = models.CharField(max_length=10,choices=REPORTING_STATUSES,default='reporting',verbose_name=_("Current status of the process"))
    time = models.DateTimeField(auto_now_add=True,verbose_name=_("Time the reporting process started"))
    response = models.TextField(blank=True,verbose_name=_("Description of any error"))
    dismissed = models.BooleanField(default=False,verbose_name=_('Has the result of this process been dismissed by the instructor?'))

    class Meta:
        verbose_name = _('report process')
        verbose_name_plural = _('report processes')
        ordering = ['-time',]

COMPLETION_STATUSES = [
    ('not attempted',_('Not started')),
    ('incomplete',_('In progress')),
    ('completed',_('Complete')),
]

class AccessToken(models.Model):
    user = models.ForeignKey(User,on_delete=models.CASCADE,related_name='access_tokens')
    resource = models.ForeignKey(Resource,on_delete=models.CASCADE,related_name='access_tokens')

    class Meta:
        verbose_name = _('access token')
        verbose_name_plural = _('access tokens')

class AccessChangeManager(models.Manager):
    use_for_related_fields = True

    def for_user(self,user):
        if user.is_anonymous:
            return AccessChange.objects.none()
        query = Q(users=user) | Q(usernames__username=user.username) | Q(emails__email__iexact=user.email)

        # When this is the RelatedManager for `Resource.access_changes`, check if there's an LTI 1.3 user alias whose sub field matches a username access change.
        if hasattr(self, 'instance') and isinstance(self.instance, Resource):
            resource = self.instance
            try:
                consumer = resource.lti_13_contexts().first().context.consumer
                query = query | Q(usernames__username__in=user.lti_13_aliases.filter(consumer=consumer).values('sub'))
            except AttributeError:
                pass

        return self.get_queryset().filter(query).distinct()

EXTEND_DURATION_UNITS = [
    ('percent', _('percent')),
    ('minutes', _('minutes')),
]

class AccessChange(models.Model):
    description = models.TextField(default='', help_text=_('Who is this for and what does it change?'))
    resource = models.ForeignKey(Resource,on_delete=models.CASCADE,related_name='access_changes')
    available_from = models.DateTimeField(blank=True, null=True, verbose_name=_('Available from'))
    available_until = models.DateTimeField(blank=True, null=True, verbose_name=_('Available until'))
    due_date = models.DateTimeField(blank=True, null=True, verbose_name=_('Due date'))
    extend_deadline = models.DurationField(blank=True, null=True, verbose_name=_('Extend deadline by'))
    max_attempts = models.PositiveIntegerField(blank=True, null=True, verbose_name=_('Maximum attempts per user'), help_text=_('Zero means unlimited attempts.'))
    extend_duration = models.FloatField(blank=True, null=True, verbose_name=_('Extend exam duration by'))
    extend_duration_units = models.CharField(max_length=10, blank=True, null=True, default='percent', choices=EXTEND_DURATION_UNITS)
    disable_duration = models.BooleanField(default=False, verbose_name=_('Disable time limit?'))
    
    require_lockdown_app = models.CharField(max_length=20, default='unchanged', blank=True, choices = [('unchanged', _('Unchanged'))] + REQUIRE_LOCKDOWN_APP_CHOICES, verbose_name=_("Require a lockdown app?"))
    lockdown_app_password = models.CharField(max_length=30, blank=True, verbose_name=_('Password for the Numbas lockdown app'))
    seb_settings = models.ForeignKey(SebSettings, blank=True, null=True, on_delete=models.SET_NULL, related_name='access_changes')

    initial_seed = models.CharField(max_length=20, default='', blank=True, verbose_name = _('Initial seed for the random number generator'))

    users = models.ManyToManyField(User, blank=True, related_name='access_changes')

    objects = AccessChangeManager()

    class Meta:
        verbose_name = _('access change')
        verbose_name_plural = _('access changes')

    def applies_to_summary(self):
        num_users = self.users.count()
        num_usernames = self.usernames.count()
        num_emails = self.emails.count()

        o = []

        if num_users>0:
            o.append(ngettext('{count} user', '{count} users',num_users).format(count=num_users))
        if num_usernames:
            o.append(ngettext('{count} username', '{count} usernames',num_usernames).format(count=num_usernames))
        if num_emails>0:
            o.append(ngettext('{count} email address', '{count} email addresses',num_emails).format(count=num_emails))

        if len(o)>0:
            return ', '.join(o)
        else:
            return _('Nobody')

    def affected_users(self):
        query_explicit_users = Q(pk__in=self.users.all())

        consumers = self.resource.lti_contexts().values('consumer')
        query_usernames = Q(lti_13_aliases__sub__in=self.usernames.values('username'), lti_13_aliases__consumer__in=consumers) | Q(lti_11_aliases__consumer_user_id__in=self.usernames.values('username'), lti_11_aliases__consumer__in=consumers)

        query_emails = Q(email__in=Subquery(self.emails.values('email')))

        return User.objects.filter(query_usernames)


    def extend_duration_string(self):
        if self.extend_duration_units == 'percent':
            return gettext('{count:g}%'.format(count=self.extend_duration))
        else:
            return ngettext('{count:g} minute','{count:g} minutes',self.extend_duration).format(count=self.extend_duration)

    def extend_duration_absolute(self, initial_duration):
        if self.extend_duration_units == 'percent':
            return self.extend_duration * initial_duration / 100
        else:
            return self.extend_duration

    def get_due_date(self):
        """
            Get the effective due date for users affected by this access change.
        """

        due_date = self.due_date if self.due_date is not None else self.resource.due_date
        if due_date is None:
            return None

        if self.extend_deadline is not None:
            due_date += self.extend_deadline

        return due_date

class UsernameAccessChange(models.Model):
    access_change = models.ForeignKey(AccessChange, on_delete=models.CASCADE, related_name='usernames')
    username = models.CharField(max_length=200)

class EmailAccessChange(models.Model):
    access_change = models.ForeignKey(AccessChange, on_delete=models.CASCADE, related_name='emails')
    email = models.EmailField()

class LTIUserData(models.Model):
    """
        Associate the LTI 1.1 data for a user with a consumer.
    """
    consumer = models.ForeignKey(LTIConsumer,on_delete=models.CASCADE,null=True)
    user = models.ForeignKey(User,on_delete=models.CASCADE,related_name='lti_data')
    resource = models.ForeignKey(Resource,on_delete=models.CASCADE)
    last_reported_score = models.FloatField(default=0)
    consumer_user_id = models.TextField(default='',blank=True,null=True)
    is_instructor = models.BooleanField(default=False)

    class Meta:
        verbose_name = _('LTI user data')
        verbose_name_plural = _('LTI user data')

    def get_source_id(self):
        try:
            if self.lti_11 and self.lti_11.lis_person_sourcedid:
                return self.lti_11.lis_person_sourcedid
            elif self.lti_13 and self.lti_13.lis_person_sourcedid:
                return self.lti_13.lis_person_sourcedid
            else:
                return self.consumer_user_id
        except LTI_11_UserData.DoesNotExist:
            return self.consumer_user_id

    def identifier(self):
        identifier_field = self.resource.lti_contexts().first().consumer.identifier_field
        if identifier_field == 'username':
            return self.get_source_id()
        elif identifier_field == 'email':
            return self.user.email
        else:
            return ''

class LTI_11_UserData(models.Model):
    user_data = models.OneToOneField(LTIUserData, on_delete=models.CASCADE, related_name='lti_11')
    lis_result_sourcedid = models.CharField(max_length=1000,default='',blank=True,null=True)
    lis_outcome_service_url = models.TextField(default='',blank=True,null=True)
    lis_person_sourcedid = models.CharField(max_length=1000,blank=True,default='',null=True)

LAUNCH_ROLE_CHOICES = [
    ('', _('Unknown')),
    ('teacher', _('Teacher')),
    ('student', _('Student')),
]

class LTILaunch(models.Model):
    """
        Record when a user launches a resource.
    """
    user = models.ForeignKey(User,on_delete=models.CASCADE,related_name='lti_launches')
    resource = models.ForeignKey(Resource,on_delete=models.CASCADE, related_name='launches')
    time = models.DateTimeField(auto_now_add=True)
    user_agent = models.CharField(max_length=500)
    ip_address = models.CharField(max_length=100)

    role = models.CharField(max_length=20, choices=LAUNCH_ROLE_CHOICES, default='', blank=True)
    lti_11_resource_link = models.ForeignKey(LTI_11_ResourceLink, on_delete=models.SET_NULL, related_name='launches', null=True)
    lti_13_resource_link = models.ForeignKey(LTI_13_ResourceLink, on_delete=models.SET_NULL, related_name='launches', null=True)

    def __str__(self):
        return 'Launch by "{}" on "{}" at {}'.format(self.user, self.resource, self.time)

    class Meta:
        verbose_name = _('LTI launch')
        verbose_name_plural = _('LTI launches')
        ordering = ('-time',)

class Attempt(models.Model):
    resource = models.ForeignKey(Resource,on_delete=models.CASCADE,related_name='attempts')
    exam = models.ForeignKey(Exam,on_delete=models.CASCADE,related_name='attempts',null=True)  # need to keep track of both resource and exam in case the exam later gets overwritten
    user = models.ForeignKey(User,on_delete=models.CASCADE,related_name='attempts')
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(blank=True,null=True)

    completion_status = models.CharField(max_length=20,choices=COMPLETION_STATUSES,default='not attempted')
    completion_status_element = models.ForeignKey("ScormElement", on_delete=models.SET_NULL, related_name="current_completion_status_of", null=True)
    scaled_score = models.FloatField(default=0)
    scaled_score_element = models.ForeignKey("ScormElement", on_delete=models.SET_NULL, related_name="current_scaled_score_of", null=True)
    sent_receipt = models.BooleanField(default=False,verbose_name=_('Has a completion receipt been sent?'))
    receipt_time = models.DateTimeField(blank=True,null=True,verbose_name=_('Time the completion receipt was sent'))

    deleted = models.BooleanField(default=False)
    broken = models.BooleanField(default=False)
    diffed = models.BooleanField(default=False)

    all_data_received = models.BooleanField(default=False)

    objects = NotDeletedManager()

    remark_ignore_keys = ['cmi.suspend_data','cmi.session_time']    # CMI keys not to resave when auto-remarking

    class Meta:
        verbose_name = ngettext('attempt','attempts',1)
        verbose_name_plural = ngettext('attempt','attempts',2)
        ordering = ['-start_time',]

    def __str__(self):
        return 'Attempt {} by "{}" on "{}"'.format(self.pk, self.user,self.resource)

    def user_data(self):
        return self.resource.user_data(self.user)

    def get_element_default(self,key,default=None):
        try:
            return self.scormelements.current(key).value
        except ScormElement.DoesNotExist:
            if callable(default):
                default = default()
            return default

    def scorm_cmi(self, include_remarked_elements=True, at_time=None):
        user_data = self.resource.user_data(self.user)
        learner_id = '' if user_data is None else user_data.identifier()

        scorm_cmi = {
            'cmi.suspend_data': '',
            'cmi.objectives._count': 0,
            'cmi.interactions._count': 0,
            'cmi.learner_name': self.user.get_full_name(),
            'cmi.learner_id': learner_id,
            'cmi.location': '',
            'cmi.score.raw': 0,
            'cmi.score.scaled': 0,
            'cmi.score.min': 0,
            'cmi.score.max': 0,
            'cmi.total_time': 0,
            'cmi.success_status': '',
            'cmi.completion_status': self.completion_status,
        }

        changes = self.resource.access_changes.for_user(self.user)

        for change in changes:
            if change.initial_seed:
                scorm_cmi['numbas.initial_seed'] = change.initial_seed

        scorm_cmi = {k: {'value':v,'time':self.start_time.timestamp()} for k,v in scorm_cmi.items()}

        # TODO only fetch the latest values of elements from the DB, somehow

        latest_elements = {}

        saved_elements = resolve_diffed_scormelements(self.scormelements.all().reverse())
        if not include_remarked_elements:
            remarked_elements = RemarkedScormElement.objects.filter(element__attempt=self).values_list('element', flat=True)
            saved_elements = [e for e in saved_elements if e.pk not in remarked_elements]

        for e in saved_elements:
            if at_time is None or e.time <= at_time + timedelta(seconds=0.1):
                latest_elements[e.key] = {'value':e.value,'time':e.time.timestamp()}

        scorm_cmi.update(latest_elements)

        return scorm_cmi

    def data_dump(self,include_all_scorm=False):
        remarked_parts = self.remarked_parts.all()
        discounted_parts = self.resource.discounted_parts.all()


        data = {
            'attempt': self.pk,
            'resource': {
                'title': self.resource.title,
                'contexts': [c.name for c in self.resource.lti_contexts()],
            },
            'exam': self.exam.pk,
            'user': {
                'pk': self.user.pk,
                'username': self.user.username,
                'first_name': self.user.first_name,
                'last_name': self.user.last_name,
            },
            'start_time': self.start_time.timestamp() if self.start_time is not None else None,
            'end_time': self.end_time.timestamp() if self.end_time is not None else None,
            'completion_status': self.completion_status,
            'scaled_score': self.scaled_score,
            'raw_score': self.raw_score,
            'scores': [],
            'broken': self.broken,
            'remarked_parts': [{'part': p.part, 'score': p.score} for p in remarked_parts],
        }

        scorm_cmi = self.scorm_cmi()
        data['scorm'] = {
            'current': scorm_cmi,
        }
        if include_all_scorm:
            all_elements = resolve_diffed_scormelements(self.scormelements.all().reverse())
            data['scorm']['all'] = [{'key': e.key, 'value': e.value, 'time': e.time.timestamp(), 'counter': e.counter} for e in all_elements]

        re_interaction_id = re.compile(r'^cmi\.interactions\.(\d+)\.id$')
        part_ids = {}
        for k,v in scorm_cmi.items():
            m = re_interaction_id.match(k)
            if m:
                part_ids[v['value']] = m.group(1)

        remark_dict = {r.part:r.score for r in remarked_parts}
        discount_dict = {d.part:d.behaviour for d in discounted_parts}

        def scorm_value(key,default=None):
            try:
                return scorm_cmi[key]['value']
            except KeyError:
                return default
        
        def describe_part(path,part={}):
            pid = part_ids.get(path)
            data = {
                'part': path,
            }
            if pid is not None:
                data.update({
                    'raw_score': float(scorm_value('cmi.interactions.{}.result'.format(pid),'0')),
                    'max_score': float(scorm_value('cmi.interactions.{}.weighting'.format(pid), '0')),
                })

            gaps = part.get('gaps',[])
            if len(gaps)>0:
                data['gaps'] = [describe_part('{}g{}'.format(path,g)) for g in gaps]
            steps = part.get('steps',[])
            if len(steps)>0:
                data['steps'] = [describe_part('{}s{}'.format(path,s)) for s in steps]

            if path in discount_dict:
                data['discounted'] = True
                behaviour = discount_dict[path]
                if behaviour == 'remove':
                    data['raw_score'] = 0
                    data['max_score'] = 0
                else:
                    data['raw_score'] = data['max_score']
                data['score_changed'] = True
            elif path in remark_dict:
                data['remarked'] = True
                data['raw_score'] = remark_dict[path]
                data['score_changed'] = True
            elif any(g.get('discounted') or g.get('remarked') for g in data.get('gaps',[])):
                raw_score = 0
                max_score = 0
                for g in data['gaps']:
                    raw_score += g['raw_score']
                    max_score += g['max_score']
                data['raw_score'] = raw_score
                data['max_score'] = max_score
                data['score_changed'] = True

            if any(s.get('discounted') or s.get('remarked') for s in data.get('steps',[])):
                step_score = 0
                for s in data['steps']:
                    step_score += s['raw_score']
                if step_score > data['raw_score']:
                    data['raw_score'] = step_score
                    data['score_changed'] = True

            return data

        for qnum, parts in self.part_hierarchy().items():
            aqs = self.question_score_info(qnum)
            obj = {
                'question': int(qnum),
                'scaled_score': aqs.scaled_score,
                'raw_score': aqs.raw_score,
                'max_score': aqs.max_score,
                'completion_status': aqs.completion_status,
                'parts': [describe_part('q{}p{}'.format(qnum,path),part) for path,part in parts.items()],
            }

            data['scores'].append(obj)

        try:
            suspend_data = json.loads(self.get_element_default('cmi.suspend_data','{}'))
        except json.decoder.JSONDecodeError:
            suspend_data = {}
        data['suspend_data'] = suspend_data

        return data

    def completed(self):
        r"""
            Should this attempt be considered as completed?

            True if:
                * completion_status = 'completed'
                * or the resource is not available to the student
                * or the due date has passed and the student has not re-opened the attempt
        """

        if self.completion_status == 'completed':
            return True

        if not self.resource.is_available(self.user):
            return True

        availability = self.resource.available_for_user(self.user)
        if availability.due_date is None or availability.due_date > timezone.now():
            return False

        return not self.student_has_reopened()

    def student_has_reopened(self):
        """
            Has the student re-opened this attempt?

            True if the most recent completion status element was created after the due date and is 'incomplete'.
        """

        availability = self.resource.available_for_user(self.user)
        if availability.due_date is None:
            return False

        try:
            e = self.scormelements.current('cmi.completion_status')
        except ScormElement.DoesNotExist:
            return True

        return e.value == 'incomplete' and e.time > availability.due_date

    def student_can_reopen(self):
        if not self.completed():
            return False

        if not self.resource.is_available(self.user):
            return False

        return self.resource.allow_student_reopen

    def get_end_time(self):
        """ When did this attempt end? Either explicitly set, or computed based on the availability and due dates for attempts which weren't ended by the student.
        """

        if not self.completed():
            return None

        # If attempt was automatically ended by the client, use the time it set.
        try:
            end_time_element = self.scormelements.current('x.end_time')
            return datetime.fromisoformat(end_time_element.value)
        except ScormElement.DoesNotExist:
            pass

        # If attempt was ended by the student, use the time that they did that.
        try:
            completion_element = self.scormelements.current('cmi.completion_status')
            if completion_element.value == 'completed':
                return completion_element.time
        except ScormElement.DoesNotExist:
            pass

        # If the attempt has implicitly ended because the due date has passed or it's unavailable, use those times.
        now = timezone.now()
        resource = self.resource
        # If the due date hasn't passed, or the student has since reopened the attempt, use the time of the last suspend data change, or the available_until, whichever is earliest
        suspend_data_elements = self.scormelements.filter(remarked=None, key='cmi.suspend_data')
        if (self.student_has_reopened() or resource.due_date is None or now < resource.due_date) and suspend_data_elements.exists():
            return min(resource.available_until, suspend_data_elements.first().time)
        # If the due date has passed, use that
        elif resource.due_date is not None:
            return resource.due_date

        return now

    def finalise(self):
        if self.end_time is None:
            self.end_time = self.get_end_time()

            self.save(update_fields=['end_time'])

            from . import tasks

            tasks.attempt_update_score_info(self,set())

            channel_layer = get_channel_layer()
            group_send = async_to_sync(channel_layer.group_send)
            group_send(group_for_attempt(self),{
                'type': 'completion_status.changed',
                'completion_status':'completed',
            })

    def reopen(self, reopened_by=None):
        e = ScormElement.objects.create(
                attempt=self,
                key='cmi.completion_status',
                value='incomplete',
                time=timezone.now(),
                counter=1
            )

        if reopened_by:
            RemarkedScormElement.objects.create(element=e, user=reopened_by)

        self.completion_status = 'incomplete'
        self.end_time = None
        self.sent_receipt = False
        self.receipt_time = None
        self.save(update_fields=('completion_status', 'end_time', 'sent_receipt', 'receipt_time',))

    @property
    def raw_score(self):
        if self.remarked_parts.exists() or self.resource.discounted_parts.exists():
            total = 0
            for i in range(self.resource.num_questions):
                total += self.question_raw_score(i)
            return total

        return float(self.get_element_default('cmi.score.raw',0))

    @property
    def max_score(self):
        if self.resource.discounted_parts.exists():
            total = 0
            for i in range(self.resource.num_questions):
                total += self.question_max_score(i)
            return total

        return float(self.get_element_default('cmi.score.max', lambda: sum(self.question_max_score(i) for i in range(self.resource.num_questions))))

    def part_discount(self,part):
        return self.resource.discounted_parts.filter(part=part).first()

    def part_paths(self):
        """ Paths to all parts in this attempt. """
        return set(e['value'] for e in self.scormelements.filter(key__regex='cmi.interactions.[0-9]+.id').values('value').distinct())

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
        paths = sorted(self.part_paths(),key=lambda x:(len(x),x))
        re_path = re.compile(r'q(\d+)p(\d+)(?:g(\d+)|s(\d+))?')
        out = defaultdict(lambda: defaultdict(lambda: {'gaps':[],'steps':[]}))
        for path in paths:
            m = re_path.match(path)
            p = out[m.group(1)][m.group(2)]
            if m.group(3):
                p['gaps'].append(m.group(3))
            elif m.group(4):
                p['steps'].append(m.group(4))

        return out

    def part_gaps(self,part):
        if not re.match(r'^q\d+p\d+$',part):
            return []
        gaps = [g for g in self.part_paths() if g.startswith(part+'g')]
        return gaps

    def part_interaction_id(self,part):
        id_element = self.scormelements.filter(key__regex='cmi.interactions.[0-9]+.id',value=part).first()
        if id_element is None:
            return None
        n = re.match(r'cmi.interactions.(\d+).id',id_element.key).group(1)
        return n

    def part_raw_score(self,part,include_remark=True):
        discounted = self.part_discount(part)
        if discounted:
            return self.part_max_score(part)

        remarked = self.remarked_parts.filter(part=part)
        if include_remark and remarked.exists():
            return remarked.last().score

        if (include_remark and self.remarked_parts.filter(part__startswith=part+'g').exists()) or self.resource.discounted_parts.filter(part__startswith=part+'g').exists():
            gaps = self.part_gaps(part)
            return sum(self.part_raw_score(g,include_remark) for g in gaps)

        id = self.part_interaction_id(part)
        if id is None:
            return 0

        score = self.get_element_default('cmi.interactions.{}.result'.format(id),0)
        return float(score)

    def part_max_score(self,part):
        discounted = self.part_discount(part)
        if discounted:
            if discounted.behaviour == 'remove':
                return 0

        if self.resource.discounted_parts.filter(part__startswith=part+'g').exists():
            gaps = self.part_gaps(part)
            return sum(self.part_max_score(g) for g in gaps)

        id = self.part_interaction_id(part)
        if id is None:
            return 0

        return float(self.get_element_default('cmi.interactions.{}.weighting'.format(id),0))

    def question_raw_score(self,n):
        _,raw,_,_ = self.calculate_question_score_info(n)
        return raw

    def calculate_question_score_info(self,n):
        qid = 'q{}'.format(n)
        if self.remarked_parts.filter(part__startswith=qid).exists() or self.resource.discounted_parts.filter(part__startswith=qid).exists():
            question_parts = [p for p in self.part_paths() if p.startswith(qid)]
            total_raw = 0.0
            total_max = 0.0
            for part in question_parts:
                if re.match(r'^q{}p\d+$'.format(n),part):
                    total_raw += self.part_raw_score(part)
                    total_max += self.part_max_score(part)
            raw_score = total_raw
            scaled_score = total_raw/total_max if total_max>0 else 0.0
            max_score = total_max
        else:
            raw_score = float(self.get_element_default('cmi.objectives.{}.score.raw'.format(n),0))
            scaled_score = float(self.get_element_default('cmi.objectives.{}.score.scaled'.format(n),0))
            max_score = float(self.get_element_default('cmi.objectives.{}.score.max'.format(n),0))

        completion_status = self.get_element_default('cmi.objectives.{}.completion_status'.format(n),'not attempted')

        return (scaled_score, raw_score, max_score, completion_status)

    def update_question_score_info(self,n):
        scaled_score,raw_score,max_score,completion_status = self.calculate_question_score_info(n)
        AttemptQuestionScore.objects.update_or_create(attempt=self,number=n,defaults={'scaled_score':scaled_score,'raw_score':raw_score,'max_score':max_score,'completion_status':completion_status})

    def question_score_info(self,n):
        try:
            return self.cached_question_scores.get(number=n)
        except AttemptQuestionScore.DoesNotExist:
            scaled_score, raw_score, max_score, completion_status = self.calculate_question_score_info(n)
            aqs, created = AttemptQuestionScore.objects.update_or_create(attempt = self, number = n, raw_score = raw_score, scaled_score = scaled_score, max_score = max_score, completion_status = completion_status)
            return aqs
        except AttemptQuestionScore.MultipleObjectsReturned:
            aqs = self.cached_question_scores.filter(number=n)
            n = aqs.count()
            aq = aqs[n]
            aqs[:n].delete()
            return aq

    def question_numbers(self):
        questions = self.scormelements.filter(key__regex='cmi.objectives.[0-9]+.id').values('key').distinct()
        re_number = re.compile(r'cmi.objectives.([0-9]+).id')
        numbers = sorted(set([re_number.match(q['key']).group(1) for q in questions]))
        return numbers

    def question_scores(self):
        return sorted([self.question_score_info(n) for n in self.question_numbers()],key=lambda x:int(x.number))

    def question_max_score(self,n):
        _,_,max_score,_ = self.calculate_question_score_info(n)
        return max_score

    def time_spent(self):
        try:
            e = self.scormelements.current('cmi.session_time')
            return parse_scorm_timeinterval(e.value)
        except ScormElement.DoesNotExist:
            return timedelta(0)

    def resume_allowed(self):
        if self.completed():
            return self.review_allowed()
        else:
            return True

    def review_allowed(self,ignore_show_scores=False):
        if not (ignore_show_scores or self.should_show_scores()):
            return False
        if self.resource.show_marks_when in ('always', 'complete'):
            return True
        return self.resource.allow_review_from is None or timezone.now() >= self.resource.allow_review_from

    def should_show_scores(self):
        if self.resource.show_marks_when == 'always':
            return True
        if self.completed():
            if self.resource.show_marks_when == 'complete':
                return True
            if self.resource.show_marks_when == 'review' and self.review_allowed(ignore_show_scores=True):
                return True
        return False

    def is_remarked(self):
        return self.remarked_parts.exists()

    def completion_receipt_context(self):
        include_score = self.should_show_scores()

        now = timezone.now()
        self.receipt_time = now

        summary = {
            'pk': self.pk,
            'receipt_time': now.isoformat(),
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
        }
        if include_score:
            summary['raw_score'] = self.raw_score

        signed_summary = signing.dumps(summary,salt=self.resource.receipt_salt())

        context = {
            'include_score': include_score,
            'receipt_time': now,
            'attempt': self,
            'resource': self.resource,
            'context': self.resource.lti_contexts().first(),
            'user': self.user,
            'signed_summary': signed_summary,
        }
        return context

    def completion_receipt(self):

        template = get_template('numbas_lti/attempt_completion_receipt.txt')

        message = template.render(self.completion_receipt_context()).strip()
        
        return message

    def send_completion_receipt(self):
        resource = self.resource
        context = resource.lti_contexts().first()
        message = self.completion_receipt()
        send_mail(
            gettext('Numbas: Receipt for {resource_name} in {context_name}').format(resource_name=resource.title, context_name=context.name),
            message,
            settings.DEFAULT_FROM_EMAIL,
            [self.user.email],
            fail_silently=False
        )
        self.sent_receipt = True
        self.save(update_fields=['sent_receipt'])
 
class AttemptLaunch(models.Model):
    attempt = models.ForeignKey(Attempt,related_name='launches', on_delete=models.CASCADE)
    time = models.DateTimeField(auto_now_add=True)
    mode = models.CharField(max_length=100)
    user = models.ForeignKey(User,blank=True,null=True,on_delete=models.CASCADE,related_name='attempt_launches')

    def __str__(self):
        return 'Launch {} in mode "{}" at {}'.format(self.attempt, self.mode, self.time)

    def as_json(self):
        return {
            'attempt': self.attempt.pk,
            'time': self.time.isoformat(),
            'mode': self.mode,
            'user': self.user.get_full_name() if self.user else None,
        }

    class Meta:
        verbose_name = _('attempt launch')
        verbose_name_plural = _('attempt launches')
        ordering = ('-time',)


class AttemptNotDeletedManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(attempt__deleted=False)

class AttemptQuestionScore(models.Model):
    attempt = models.ForeignKey(Attempt,related_name='cached_question_scores', on_delete=models.CASCADE)
    number = models.IntegerField()
    raw_score = models.FloatField()
    scaled_score = models.FloatField()
    max_score = models.FloatField()
    completion_status = models.CharField(default='not attempted',max_length=20)

    objects = AttemptNotDeletedManager()

    class Meta:
        verbose_name = _('question score')
        verbose_name_plural = _('question scores')
        unique_together = (('attempt','number'),)

    def __str__(self):
        return '{}/{} on question {} of {}'.format(self.raw_score,self.max_score,self.number,self.attempt)

class RemarkPart(models.Model):
    attempt = models.ForeignKey(Attempt,related_name='remarked_parts', on_delete=models.CASCADE)
    part = models.CharField(max_length=20)
    score = models.FloatField(default=0)

    class Meta:
        verbose_name = _('remarked part')
        verbose_name_plural = _('remarked parts')
    
    def __str__(self):
        return '{} on part {} in {}'.format(self.score, self.part, self.attempt)

DISCOUNT_BEHAVIOURS = [
    ('remove',_('Remove from total')),
    ('fullmarks',_('Award everyone full credit')),
]

class DiscountPart(models.Model):
    resource = models.ForeignKey(Resource,related_name='discounted_parts', on_delete=models.CASCADE)
    part = models.CharField(max_length=20)
    behaviour = models.CharField(max_length=10,choices=DISCOUNT_BEHAVIOURS,default='remove')

    class Meta:
        verbose_name = _('discounted part')
        verbose_name_plural = _('discounted parts')

class ScormElementQuerySet(models.QuerySet):
    def current(self,key):
        """ Return the last value of this field """
        elements = self.filter(key=key)
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
    time = models.DateTimeField()
    counter = models.IntegerField(default=0,verbose_name=_('Element counter to disambiguate elements with the same timestamp'))
    current = models.BooleanField(default=True) # is this the latest version?

    class Meta:
        verbose_name = _('SCORM element')
        verbose_name_plural = _('SCORM elements')
        ordering = ['-time','-counter','-pk',]

    def __str__(self):
        return '{}: {}'.format(self.key,self.value[:50]+(self.value[50:] and '...'))

    def newer_than(self, other):
        if other is None:
            return True
        return self.time>other.time or (self.time==other.time and self.counter>other.counter)

    def as_json(self):
        return {
            'pk': self.pk,
            'key': self.key,
            'value': self.value,
            'time': self.time.isoformat(),
            'counter': self.counter,
        }

class ScormElementDiff(models.Model):
    element = models.OneToOneField('ScormElement', on_delete=models.CASCADE, related_name='diff')
    diff_of = models.OneToOneField('ScormElement', on_delete=models.PROTECT, related_name='diffs')

    class Meta:
        verbose_name = _('SCORM element diff')
        verbose_name_plural = _('SCORM element diffs')

def diff_scormelements(attempt, key='cmi.suspend_data'):
    """
        For SCORM elements for the given attempt with the given key, replace the full value with a diff, relative to the most recent value.
        The most recent ScormElement object has the full value saved, so it can be read off easily, but the earlier values are stored as diffs to save on space.
    """
    elements = attempt.scormelements.filter(key=key,diff=None)
    last = None
    with transaction.atomic():
        for e in sorted(elements, key=lambda x: hasattr(x,'diffs')):
            value = e.value
            if last is not None and not e.newer_than(last):
                d = make_diff(lastvalue,e.value)
                e.value = d
                ScormElementDiff.objects.get_or_create(element=e,diff_of=last)
                e.save()
            last = e
            lastvalue = value
            if hasattr(e,'diffs'):
                break
        attempt.diffed = True
        attempt.save()

def resolve_dependency_order(deps):
    order = list(deps.keys())
    i = 0
    step = 0
    l = len(order)
    while i<l:
        step += 1
        if step>l*l:
            raise Exception("There's a loop in the dependency chain of diffed SCORM elements")
        a = order[i]
        if a in deps:
            b = deps[a]
            if b in order:
                j = order.index(b)
                if j<i:
                    order.pop(j)
                    order.append(b)
                    i -= 1
        i += 1
    return list(reversed(order))

def resolve_diffed_scormelements(elements):
    if isinstance(elements,models.QuerySet):
        elements = elements.select_related('diff')
    elements = list(elements)
    emap = {e.pk: e for e in elements}
    diffmap = {}
    for e in elements:
        try:
            diffmap[e.pk] = e.diff.diff_of.pk
        except ObjectDoesNotExist:
            pass
    order = resolve_dependency_order(diffmap)
    for p in order:
        e1 = emap[p]
        e2 = emap[e1.diff.diff_of.pk]
        e1.value = apply_diff(e1.value, e2.value)
        
    return elements

class RemarkedScormElement(models.Model):
    element = models.OneToOneField(ScormElement,on_delete=models.CASCADE,related_name='remarked')
    user = models.ForeignKey(User,on_delete=models.SET_NULL,null=True,related_name='remarked_elements')

    class Meta:
        verbose_name = _('remarked SCORM element')
        verbose_name_plural = _('remarked SCORM element')

    def as_json(self):
        return {
            'element': self.element.pk,
            'user': self.user.get_full_name(),
        }

class EditorLink(models.Model):
    name = models.CharField(max_length=200,verbose_name=_('Editor name'))
    url = models.URLField(verbose_name=_('Base URL of the editor'),unique=True)
    cached_available_exams = models.TextField(blank=True,editable=False,verbose_name=_('Cached JSON list of available exams from this editor'))
    last_cache_update = models.DateTimeField(null=True,blank=True,editable=False,verbose_name=_('Time of last cache update'))

    class Meta:
        verbose_name = _('editor link')
        verbose_name_plural = _('editor links')

    def __str__(self):
        return self.name

    def update_cache(self,bounce=True):
        if bounce and self.time_since_last_update().seconds<30:
            return

        if self.projects.exists():
            project_pks = [str(p.remote_id) for p in self.projects.all()]
            r = requests.get('{}/api/available-exams'.format(self.url), params={'projects':project_pks})

            self.cached_available_exams = r.text
        else:
            self.cached_available_exams = '[]'
        self.last_cache_update = timezone.now()

    def time_since_last_update(self):
        if self.last_cache_update is None:
            return timedelta.max
        return timezone.now() - self.last_cache_update

    @property
    def available_exams(self):
        if self.time_since_last_update().seconds> 30:
            from . import tasks
            tasks.editorlink_update_cache(self)
        if self.cached_available_exams:
            return json.loads(self.cached_available_exams)
        else:
            return []

class EditorLinkProject(models.Model):
    editor = models.ForeignKey(EditorLink,on_delete=models.CASCADE,related_name='projects',verbose_name=_('Editor that this project belongs to'))
    name = models.CharField(max_length=200,verbose_name=_('Name of the project'))
    description = models.TextField(blank=True,verbose_name=_('Description of the project'))
    remote_id = models.IntegerField(verbose_name=_('ID of the project on the editor'))
    homepage = models.URLField(verbose_name=_('URL of the project\'s homepage on the editor'))
    rest_url = models.URLField(verbose_name=_('URL of the project on the editor\'s REST API'))

    class Meta:
        verbose_name = _('linked editor project')
        verbose_name_plural = _('linked editor project')
        ordering = ['name']

    def __str__(self):
        return self.name

class StressTest(models.Model):
    resource = models.OneToOneField(Resource,on_delete=models.CASCADE,primary_key=True)

    class Meta:
        verbose_name = _('stress test')
        verbose_name_plural = _('stress tests')
        ordering = ['-resource__creation_time']

    def __str__(self):
        return self.resource.creation_time.strftime('%B %d, %Y %H:%M')

    def get_absolute_url(self):
        return reverse('view_stresstest',args=(self.pk,))

class StressTestNote(models.Model):
    stresstest = models.ForeignKey(StressTest,on_delete=models.CASCADE,related_name='notes')
    text = models.TextField()
    time = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('stress test note')
        verbose_name_plural = _('stress test notes')

FILE_REPORT_STATUSES = [
    ('inprogress', _('In progress')),
    ('complete', _('Complete')),
    ('error', _('Error')),
]

class FileReport(models.Model):
    name = models.CharField(max_length=300)
    resource = models.ForeignKey(Resource, null=True, on_delete=models.CASCADE, related_name='file_reports')
    outfile = models.FileField(upload_to='reports/', verbose_name='Output file')
    status = models.CharField(max_length=10, default='inprogress', choices=FILE_REPORT_STATUSES)
    creation_time = models.DateTimeField(auto_now_add=True, verbose_name=_('Time this report was created'))
    created_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name='file_reports')

    class Meta:
        verbose_name = _('Report file')
        verbose_name_plural = _('Report files')
        ordering = ('-creation_time',)

    def expiry_date(self):
        return self.creation_time + timedelta(days=settings.REPORT_FILE_EXPIRY_DAYS)


class UserScoreReported(models.Model):
    """
        A record of the fact that a student's score for a resource was reported back to the consumer.
    """
    user = models.ForeignKey(User,on_delete=models.CASCADE,related_name='reported_scores')
    resource = models.ForeignKey(Resource,on_delete=models.CASCADE,related_name='user_scores_reported')
    attempt = models.ForeignKey(Attempt, on_delete=models.SET_NULL, null=True, help_text=_('Attempt whose score was used for this report.'))
    report_process = models.ForeignKey(ReportProcess, on_delete=models.SET_NULL, null=True, help_text=_('Resource score reporting process that this was a part of.'), related_name='user_score_reports')
    time = models.DateTimeField(auto_now_add=True, help_text=_('The time that the score was reported.'))
    error = models.TextField(blank=True, null=True, verbose_name=_('Error message'), help_text=_('The text of any error message returned by the consumer.'))
    raw_score = models.FloatField()
    max_score = models.FloatField()
    completion_status = models.CharField(max_length=20,choices=COMPLETION_STATUSES)
    start_time = models.DateTimeField()
    submitted_time = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('time',)

    def __str__(self):
        s = _('Score of {raw_score}/{max_score} ({completion_status}) by {user_name} on {resource} reported at {time}').format(raw_score=self.raw_score, max_score=self.max_score, completion_status=self.completion_status, user_name=self.user.get_full_name(), resource=str(self.resource), time=self.time)
        if self.submitted_time is not None:
            s += _(' submitted at {submitted_time}').format(submitted_time=self.submitted_time)
        if self.error:
            s += _(' failed: {error_msg}').format(error_msg=self.error)
        return s
