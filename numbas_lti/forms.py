from django.forms import ModelForm

from .models import Resource, DiscountPart, RemarkPart, LTIConsumer

from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

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
