import zipfile

from django.forms import ModelForm
from django import forms
from django.utils.translation import ugettext_lazy as _

from .models import Exam, Resource, DiscountPart, RemarkPart, LTIConsumer, EditorLink, EditorLinkProject, ConsumerTimePeriod

from django.core.files import File
from io import BytesIO

from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
import os
import requests
import json

from django.utils.crypto import get_random_string
import string

class ResourceSettingsForm(ModelForm):
    class Meta:
        model = Resource
        fields = ['grading_method','include_incomplete_attempts','max_attempts','show_marks_when','report_mark_time']

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
        fields = ('key','url',)

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

    def save(self,commit=True):
        exam = super(CreateExamForm,self).save(commit=False)
        retrieve_url = self.cleaned_data.get('retrieve_url')
        if retrieve_url:
            zip = requests.get(retrieve_url+'?scorm').content
            exam.retrieve_url = retrieve_url
            exam.package.save('exam.zip',File(BytesIO(zip)))
        if commit:
            exam.save()
        return exam

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
            response = requests.get('{}/api/handshake'.format(url))
            if response.status_code != 200:
                raise Exception("Request returned HTTP status code {}.".format(response.status_code))
            data = response.json()
            if data.get('numbas_editor')!=1:
                raise Exception("This doesn't seem to be a Numbas editor instance.")
            self.cleaned_data['name'] = data['site_title']
        except (Exception,json.JSONDecodeError,requests.exceptions.RequestException) as e:
            raise forms.ValidationError("There was an error connecting to this URL: {}".format(e))
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
