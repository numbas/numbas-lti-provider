from django.forms import ModelForm

from .models import Resource, DiscountPart, RemarkPart

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
