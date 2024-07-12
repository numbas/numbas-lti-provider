import zipfile
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from django.conf import settings
from django.forms import ModelForm, Form
import django.forms.renderers
from django import forms, utils
from django.utils.translation import gettext_lazy as _

from . import requests_session
from .models import Exam, Resource, DiscountPart, RemarkPart, LTIConsumer, LTIConsumerRegistrationToken, LTI_11_Consumer, EditorLink, EditorLinkProject, ConsumerTimePeriod, AccessChange, UsernameAccessChange, EmailAccessChange, SebSettings, LTI_13_ResourceLink, register_lti_13_tool
from .test_exam import test_zipfile, ExamTestException

from django.core.files import File
from io import BytesIO

from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
import os
import requests
import json
from datetime import timedelta

from django.utils.crypto import get_random_string
from django.utils.formats import get_format
import string

from pylti1p3.contrib.django.lti1p3_tool_config.models import LtiTool

datetime_format = get_format('DATETIME_INPUT_FORMATS')[0]

def split_newlines_commas(text):
    items = [x.strip() for x in sum((l.split(',') for l in text.split('\n')),[])]
    return [x for x in items if x!='']

class MultipleStringField(forms.MultipleChoiceField):
    """
        A field that accepts any list of strings.
    """

    def valid_value(self, value):
        return True

class DateTimeInput(forms.DateTimeInput):
    input_type = 'datetime-local'

class AccessChangeForm(ModelForm):

    nrps_applies_to = MultipleStringField(required=False, label=_('Usernames'))
    usernames = forms.CharField(required=False, label=_('Usernames'), widget=forms.Textarea(attrs={'rows':5}), help_text=_('Enter usernames, separated by commas or one on each line.'))
    emails = forms.CharField(required=False, label=_('Email addresses'), widget=forms.Textarea(attrs={'rows':5}), help_text=_('Enter email addresses, separated by commas or one on each line.'))
    extend_deadline_days = forms.IntegerField(required=False, label=_('days'), widget=forms.NumberInput())
    extend_deadline_minutes = forms.IntegerField(required=False, label=_('minutes'), widget=forms.NumberInput())

    class Meta:
        model = AccessChange
        fields = [
            'description',
            'resource',
            'available_from',
            'available_until',
            'max_attempts',
            'extend_duration',
            'extend_duration_units',
            'disable_duration',
            'require_lockdown_app',
            'lockdown_app_password',
            'seb_settings',
        ]
        widgets = {
            'description': forms.TextInput(),
            'available_from': DateTimeInput(format=datetime_format),
            'available_until': DateTimeInput(format=datetime_format),
            'extend_duration': forms.TextInput(),
            'extend_duration_units': forms.Select(),
            'resource': forms.HiddenInput(),
        }

    def save(self, commit=True):
        ac = super().save(commit=False)

        extend_deadline_days = self.cleaned_data['extend_deadline_days']
        extend_deadline_minutes = self.cleaned_data['extend_deadline_minutes']
        extend_deadline = timedelta(0)
        if extend_deadline_days is not None:
            extend_deadline += timedelta(days=extend_deadline_days)
        if extend_deadline_minutes is not None:
            extend_deadline += timedelta(minutes=extend_deadline_minutes)
        if extend_deadline>timedelta(0):
            ac.extend_deadline = extend_deadline
        else:
            ac.extend_deadline = None

        if commit:
            ac.save()
            nrps_usernames = self.cleaned_data['nrps_applies_to']
            text_usernames = split_newlines_commas(self.cleaned_data['usernames'])
            usernames = text_usernames + nrps_usernames
            ac.usernames.exclude(username__in=usernames).delete()
            new_usernames = set(usernames) - set(ac.usernames.values_list('username',flat=True))
            for username in new_usernames:
                UsernameAccessChange.objects.create(access_change = ac, username=username)

            emails = split_newlines_commas(self.cleaned_data['emails'])
            ac.emails.exclude(email__in=emails).delete()
            new_emails = set(emails) - set(ac.emails.values_list('email',flat=True))
            for email in new_emails:
                EmailAccessChange.objects.create(access_change = ac, email=email)

            ac.resource.send_access_changes()

        return ac

class FieldsetFormMixin:
    template_name = 'numbas_lti/fieldset_form.html'

    def fieldsets(self):
        for label, fieldnames in self.Meta.fieldsets:
            yield (label, [self[fieldname] for fieldname in fieldnames if fieldname in self.fields])

class ResourceSettingsForm(FieldsetFormMixin, ModelForm):
    class Meta:
        model = Resource
        fields = ['grading_method','include_incomplete_attempts','max_attempts','show_marks_when','report_mark_time','allow_review_from','available_from','available_until','email_receipts','require_lockdown_app', 'lockdown_app_password', 'seb_settings', 'show_lockdown_app_password']
        fieldsets = [
            (_('Grading'), ('grading_method', 'include_incomplete_attempts',)),
            (_('Attempts'), ('max_attempts',)),
            (_('Feedback'), ('show_marks_when', 'report_mark_time', 'allow_review_from', 'email_receipts',)),
            (_('Availability'), ('available_from', 'available_until')),
            (_('Lockdown app'), ('require_lockdown_app', 'lockdown_app_password', 'seb_settings', 'show_lockdown_app_password')),
        ]
        widgets = {
            'allow_review_from': DateTimeInput(format=datetime_format),
            'available_from': DateTimeInput(format=datetime_format),
            'available_until': DateTimeInput(format=datetime_format),
            'lockdown_app_password': forms.TextInput(attrs={'placeholder': getattr(settings,'LOCKDOWN_APP',{}).get('password','')}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not getattr(settings,'EMAIL_COMPLETION_RECEIPTS',False):
            del self.fields['email_receipts']

class RemarkPartScoreForm(ModelForm):
    class Meta:
        model = RemarkPart
        fields =['score']

class DiscountPartBehaviourForm(ModelForm):
    class Meta:
        model = DiscountPart
        fields =['behaviour']

class CreateSuperuserForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('username','first_name','last_name')

    def save(self,commit=True):
        user = super(CreateSuperuserForm,self).save(commit=False)
        user.is_superuser = True
        user.is_staff = True
        if commit:
            user.save()
        return user

class CreateConsumerForm(ModelForm):
    key = forms.CharField(strip=True,widget=forms.TextInput())

    class Meta:
        model = LTIConsumer
        fields = ('url','identifier_field',)

    def save(self,commit=True):
        consumer = super(CreateConsumerForm,self).save(commit=False)
        if commit:
            consumer.save()
            key = self.cleaned_data['key']
            lti_11_consumer = LTI_11_Consumer.objects.create(
                consumer=consumer,
                key=key,
                secret=get_random_string(20,allowed_chars = string.ascii_lowercase+string.digits)
            )
        return consumer

class CreateRegistrationTokenForm(ModelForm):
    class Meta:
        model = LTIConsumerRegistrationToken
        fields = ('name',)

class LTI_13_LinkResourceForm(ModelForm):
    class Meta:
        model = LTI_13_ResourceLink
        fields = ('resource_link_id', 'title', 'description', 'context')

    def save(self, commit=True):
        if commit:
            try:
                resource = self.instance.resource
            except Resource.DoesNotExist:
                resource = Resource.objects.create(title = self.cleaned_data['title'], description=self.cleaned_data['description'])
                self.instance.resource = resource

        return super().save(commit=commit)

class CreateExamForm(ModelForm):
    package = forms.FileField(required=False)

    class Meta:
        model = Exam
        fields = ['package','retrieve_url','rest_url']
        widgets = {
            'retrieve_url': forms.HiddenInput(),
            'rest_url': forms.HiddenInput(),
        }

    def clean_package(self):
        package = self.cleaned_data['package']
        if package is not None:
            try:
                zip = zipfile.ZipFile(package)
                zip.getinfo('imsmanifest.xml')
            except zipfile.BadZipFile:
                raise forms.ValidationError(_("The uploaded file is not a .zip file"))
            except KeyError:
                raise forms.ValidationError(_("The uploaded .zip file does not contain an imsmanifest.xml file - make sure you download a SCORM package from the editor."))

        return package

    def clean(self):
        cleaned_data = super().clean()
        package = cleaned_data.get('package')
        retrieve_url = cleaned_data.get('retrieve_url')
        if package is None:
            if not retrieve_url:
                raise forms.ValidationError(_("You must upload a file."))
            scheme, netloc, path, params, qs, fragment = urlparse(retrieve_url)
            query = parse_qs(qs)
            query.setdefault('scorm','')
            retrieve_url = urlunparse((scheme, netloc, path, params, urlencode(query,True), fragment))
            package_bytes = requests_session.get_session().get(retrieve_url,timeout=getattr(settings,'REQUEST_TIMEOUT',60)).content
            cleaned_data['package'] = File(BytesIO(package_bytes),name='exam.zip')

        if getattr(settings,'TEST_UPLOADED_EXAMS',False) and hasattr(settings,'NUMBAS_TESTING_FRAMEWORK_PATH'):
            try:
                test_zipfile(zipfile.ZipFile(cleaned_data['package'].file))
            except ExamTestException as e:
                raise forms.ValidationError(_("There was an error while testing this exam package:") + "<pre>{}</pre>".format(utils.html.escape(e)))

        return cleaned_data

class ReplaceExamForm(CreateExamForm):
    safe_replacement = forms.BooleanField(required=False,label=_('Make existing attempts use this version'))

class RestoreExamForm(ModelForm):
    class Meta:
        model = Resource
        fields = ('exam',)

class EditorLinkProjectForm(ModelForm):
    use = forms.BooleanField(required=False)
    class Meta:
        model = EditorLinkProject
        fields=('name','description','remote_id','homepage','rest_url')
        widgets = {
            'name': forms.HiddenInput(),
            'description': forms.HiddenInput(),
            'remote_id': forms.HiddenInput(),
            'homepage': forms.HiddenInput(),
            'rest_url': forms.HiddenInput(),
        }

class CreateEditorLinkForm(ModelForm):
    class Meta:
        model = EditorLink
        fields = ['url']

    def clean_url(self):
        url = self.cleaned_data['url']
        try:
            response = requests_session.get_session().get('{}/api/handshake'.format(url), timeout=getattr(settings,'REQUEST_TIMEOUT',60))
            if response.status_code != 200:
                raise Exception(_("Request returned HTTP status code") + " {}.".format(response.status_code))
            data = response.json()
            if data.get('numbas_editor')!=1:
                raise Exception(_("This doesn't seem to be a Numbas editor instance."))
            self.cleaned_data['name'] = data['site_title']
        except (Exception,json.JSONDecodeError,requests.exceptions.RequestException) as e:
            raise forms.ValidationError(_("There was an error connecting to this URL:") + " {}".format(e))
        return url

    def save(self,commit=True):
        editorlink = super(CreateEditorLinkForm,self).save(commit=False)
        editorlink.name = self.cleaned_data['name']
        if commit:
            editorlink.save()
        return editorlink

class ConsumerTimePeriodForm(ModelForm):
    class Meta:
        model = ConsumerTimePeriod
        fields = ['name','start','end']
        widgets = {
            'name': forms.TextInput(),
            'start': forms.DateInput(attrs={'type':'date'}),
            'end': forms.DateInput(attrs={'type':'date'}),
        }

ConsumerTimePeriodFormSet = forms.inlineformset_factory(LTIConsumer, ConsumerTimePeriod, form=ConsumerTimePeriodForm, can_delete=False)

class ValidateReceiptForm(Form):
    code = forms.CharField(strip=True,widget=forms.Textarea())

class CreateSebSettingsForm(ModelForm):
    class Meta:
        model = SebSettings
        fields = ('name', 'config_key_hash', 'password', 'settings_file')

class DeploymentIdWidget(forms.TextInput):
    def format_value(self, value):
        if value is None:
            return ''
        value = json.loads(value)
        if len(value) > 0:
            return value[0]
        else:
            return ''

    def value_from_datadict(self, data, files, name):
        return json.dumps([data[name]])

    def value(self):
        value = super().value()
        return [value]

class CanvasLti13RegistrationForm(FieldsetFormMixin, ModelForm):
    preset = forms.ChoiceField(
        choices=[(k, v['label']) for k,v in settings.CANVAS_LTI_13_PRESETS.items()] + [('custom', _('Custom'))],
        label=_('Preset')
    )

    class Meta:
        model = LtiTool
        fields = ['issuer', 'auth_login_url', 'auth_token_url', 'key_set_url', 'client_id','deployment_ids', 'title',]

        fieldsets = [
            (_('Issuer settings'), ('preset', 'issuer', 'key_set_url', 'auth_login_url', 'auth_token_url',)),
            (_('IDs'), ('title', 'client_id', 'deployment_ids',)),
        ]

        widgets = {
            'deployment_ids': DeploymentIdWidget()
        }

class BlackboardLti13RegistrationForm(Form):
    client_id = forms.CharField(label=_('Client ID'))
    deployment_id = forms.CharField(label=_('Deployment ID'))

    def clean_client_id(self):
        client_id = self.cleaned_data['client_id']
        try:
            tool = LtiTool.objects.get(issuer='https://blackboard.com', client_id=client_id)
            self.cleaned_data['tool'] = tool
        except LtiTool.DoesNotExist:
            try:
                tool = LtiTool.objects.get(issuer='https://developer.blackboard.com/', client_id=client_id)
                tool.pk = None
                tool.issuer = 'https://blackboard.com'
                tool.deployment_ids = []
                tool.save()

                self.cleaned_data['tool'] = tool

            except LtiTool.DoesNotExist:
                raise forms.ValidationError(_("An LTI tool with that client ID has not been registered. Check that you have completed the dynamic registration process."))

        return client_id
