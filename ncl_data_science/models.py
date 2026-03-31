from django.db import models
from numbas_lti.models import Resource, Attempt


def progress_for_resource(resource, user):
    blank_progress = {
        'completion_status': 'not attempted',
        'submitted_at': None,
        'scaled_score': 0,
    }

    if resource is None:
        return blank_progress

    grade = resource.grade_user(user)

    if grade is None:
        return blank_progress
    else:
        attempt, completion_status, submitted_at = grade
        return {
            'completion_status': completion_status,
            'submitted_at': submitted_at,
            'scaled_score': attempt.scaled_score,
        }


status_values = ['not attempted', 'incomplete', 'completed']


def max_completion_status(statuses):
    try:
        return status_values[max(status_values.index(status) for status in statuses)]
    except ValueError:
        return status_values[0]


class Topic(models.Model):
    name = models.CharField(max_length=500)
    description = models.TextField()
    image = models.ImageField(upload_to='ncl_data_science/topics')

    def __str__(self):
        return self.name

    def progress_for_user(self, user):
        resources = Resource.objects.filter(data_science_subtopics__in=self.subtopics.all())
        attempts = Attempt.objects.filter(resource__in=resources, user=user)
        completions = []
        for r in resources:
            r_completion = max_completion_status(a.completion_status for a in attempts if a.resource == r)
            completions.append(r_completion)

        if set(completions).issubset({'completed'}):
            completion_status = 'completed'
        elif set(completions).issubset({'not attempted'}):
            completion_status = 'not attempted'
        else:
            completion_status = 'incomplete'

        scaled_score = 1 if len(completions)==0 else len([x for x in completions if x=='cmpleted'])/len(completions)

        return {
            'completion_status': completion_status,
            'scaled_score': scaled_score,
        }


class HasProgressMixin:
    def progress_for_user(self, user):
        return progress_for_resource(self.resource, user)


class Subtopic(models.Model, HasProgressMixin):
    name = models.CharField(max_length=500)
    resource = models.ForeignKey(Resource, null=True, blank=True, related_name='data_science_subtopics', on_delete=models.SET_NULL)
    topic = models.ForeignKey(Topic, related_name='subtopics', on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class CaseStudy(models.Model, HasProgressMixin):
    name = models.CharField(max_length=500)
    difficulty = models.IntegerField()
    description = models.TextField()
    image = models.ImageField(upload_to='ncl_data_science/case_studies')
    topics = models.ManyToManyField(Topic, blank=True, related_name='case_studies', through='CaseStudyTopic')
    resource = models.ForeignKey(Resource, null=True, blank=True, related_name='data_science_case_studies', on_delete=models.SET_NULL)

    class Meta:
        verbose_name = 'Case study'
        verbose_name_plural = 'Case studies'

    def __str__(self):
        return self.name

    def main_topics(self):
        return Topic.objects.filter(pk__in=CaseStudyTopic.objects.filter(case_study=self, is_extension=False).values_list('topic'))

    def extension_topics(self):
        return Topic.objects.filter(pk__in=CaseStudyTopic.objects.filter(case_study=self, is_extension=True).values_list('topic'))


class CaseStudyTopic(models.Model):
    case_study = models.ForeignKey(CaseStudy, on_delete=models.CASCADE)
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
    is_extension = models.BooleanField(default=False)


