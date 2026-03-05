from django.db import models
from numbas_lti.models import Attempt
import uuid

def student_file_upload_to(instance, filename):
    return f'student_files/attempt/{instance.attempt.pk}/{instance.pk}/{filename}'

# Create your models here.
class StudentFile(models.Model):
    uid = models.UUIDField(default = uuid.uuid4, primary_key = True)
    attempt = models.ForeignKey(Attempt, related_name='uploaded_files', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now=True)
    file = models.FileField(upload_to=student_file_upload_to)
    part = models.CharField(max_length=50)

    def __str__(self):
        return f'{self.file.name} in attempt {self.attempt}'
