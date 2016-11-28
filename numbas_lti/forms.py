from django.forms import ModelForm
from django import forms

from .models import Exam, Resource, DiscountPart, RemarkPart, LTIConsumer

from django.core.files import File
from io import BytesIO

from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
import os
import requests

from django.utils.crypto import get_random_string
import string

class ResourceSettingsForm(ModelForm):
    class Meta:
        model = Resource
        fields = ['grading_method','include_incomplete_attempts','max_attempts','show_incomplete_marks','report_mark_time']

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
        fields = ('key',)

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

    def clean(self):
        cleaned_data = super(CreateExamForm,self).clean()
        if not (cleaned_data.get('retrieve_url') or cleaned_data.get('package')):
            raise forms.ValidationError("No exam selected")

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
