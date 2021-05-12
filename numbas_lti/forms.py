import zipfile
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from django.conf import settings
from django.forms import ModelForm, Form
from django import forms, utils
from django.utils.translation import ugettext_lazy as _

from .models import Exam, Resource, DiscountPart, RemarkPart, LTIConsumer, EditorLink, EditorLinkProject, ConsumerTimePeriod, AccessChange, UsernameAccessChange, EmailAccessChange
from .test_exam import test_zipfile, ExamTestException

from django.core.files import File
from io import BytesIO

from django.contrib.auth.forms import UserCreationForm
import bootstrap_datepicker_plus
from django.contrib.auth.models import User
import os
import requests
import json
from datetime import timedelta

from django.utils.crypto import get_random_string
from django.utils.formats import get_format
import string

datetime_format = get_format('DATETIME_INPUT_FORMATS')[0]

class DateTimePickerInput(bootstrap_datepicker_plus.DateTimePickerInput):
    _default_options = dict(bootstrap_datepicker_plus.DateTimePickerInput._default_options, **{
        'sideBySide': True,
        'useCurrent': False,
    })

def split_newlines_commas(text):
    items = [x.strip() for x in sum((l.split(',') for l in text.split('\n')),[])]
    return [x for x in items if x!='']

class AccessChangeForm(ModelForm):

    usernames = forms.CharField(required=False, label=_('Usernames'), widget=forms.Textarea(attrs={'rows':5}), help_text=_('Enter usernames, separated by commas or one on each line.'))
    emails = forms.CharField(required=False, label=_('Email addresses'), widget=forms.Textarea(attrs={'rows':5}), help_text=_('Enter email addresses, separated by commas or one on each line.'))
    extend_deadline_days = forms.IntegerField(required=False, label=_('days'), widget=forms.NumberInput(attrs={'class':'form-control'}))
    extend_deadline_minutes = forms.IntegerField(required=False, label=_('minutes'), widget=forms.NumberInput(attrs={'class':'form-control'}))

    class Meta:
        model = AccessChange
        fields = ['description','resource','available_from', 'available_until', 'max_attempts', 'extend_duration', 'extend_duration_units']
        widgets = {
            'description': forms.TextInput(),
            'available_from': DateTimePickerInput(format=datetime_format),
            'available_until': DateTimePickerInput(format=datetime_format),
            'extend_duration': forms.TextInput(attrs={'class':'form-control'}),
            'extend_duration_units': forms.Select(attrs={'class':'form-control'}),
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
            usernames = split_newlines_commas(self.cleaned_data['usernames'])
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

class ResourceSettingsForm(ModelForm):
    class Meta:
        model = Resource
        fields = ['grading_method','include_incomplete_attempts','max_attempts','show_marks_when','report_mark_time','allow_review_from','available_from','available_until','email_receipts']
        widgets = {
            'allow_review_from': DateTimePickerInput(format=datetime_format),
            'available_from': DateTimePickerInput(format=datetime_format),
            'available_until': DateTimePickerInput(format=datetime_format),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not settings.EMAIL_COMPLETION_RECEIPTS:
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
    class Meta:
        model = LTIConsumer
        fields = ('key','url','identifier_field',)

    def save(self,commit=True):
        consumer = super(CreateConsumerForm,self).save(commit=False)
        consumer.secret = get_random_string(20,allowed_chars = string.ascii_lowercase+string.digits)
        if commit:
            consumer.save()
        return consumer

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
        if package is None and retrieve_url:
            scheme, netloc, path, params, qs, fragment = urlparse(retrieve_url)
            query = parse_qs(qs)
            query.setdefault('scorm','')
            retrieve_url = urlunparse((scheme, netloc, path, params, urlencode(query,True), fragment))
            package_bytes = requests.get(retrieve_url,timeout=getattr(settings,'REQUEST_TIMEOUT',60)).content
            cleaned_data['package'] = File(BytesIO(package_bytes),name='exam.zip')

        if getattr(settings,'TEST_UPLOADED_EXAMS',False) and hasattr(settings,'NUMBAS_TESTING_FRAMEWORK_PATH'):
            try:
                test_zipfile(zipfile.ZipFile(cleaned_data['package'].file))
            except ExamTestException as e:
                raise forms.ValidationError(_("There was an error while testing this exam package:") + "<pre>{}</pre>".format(utils.html.escape(e)))

        return cleaned_data

class ReplaceExamForm(CreateExamForm):
    safe_replacement = forms.BooleanField(required=False,label=_('This is a safe replacement for the previous exam package'))

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
            response = requests.get('{}/api/handshake'.format(url), timeout=getattr(settings,'REQUEST_TIMEOUT',60))
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
            'name': forms.TextInput(attrs={'class':'form-control'}),
            'start': forms.DateInput(attrs={'class':'form-control','type':'date'}),
            'end': forms.DateInput(attrs={'class':'form-control','type':'date'}),
        }

ConsumerTimePeriodFormSet = forms.inlineformset_factory(LTIConsumer, ConsumerTimePeriod, form=ConsumerTimePeriodForm, can_delete=False)

class ValidateReceiptForm(Form):
    code = forms.CharField(strip=True,widget=forms.Textarea(attrs={'class':'form-control'}))
