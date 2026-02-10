from django.db import transaction
from django.core.files import File
from django.core.management.base import BaseCommand
from collections import defaultdict
import os
import json
import shutil
import subprocess
import datetime
from django.utils.timezone import make_aware, datetime
import uuid

from numbas_lti.models import Exam, Resource, User, Attempt, ScormElement, AttemptQuestionScore
from numbas_lti.test_exam import test_exam, ExamTestException

def new_user():
    username = uuid.uuid4().hex
    first_name = username[:5]
    last_name = username[5:10]

    return User.objects.create(username=username, first_name=first_name, last_name=last_name)

users = defaultdict(new_user)

def tt(s):
    if s is None:
        return None
    return make_aware(datetime.fromtimestamp(s))

class Command(BaseCommand):
    help = 'Test an exam package'

    def add_arguments(self, parser):
        parser.add_argument('exam_file',type=str)
        parser.add_argument('attempts_file',type=str)

    def handle(self, *args, **options):
        shutil.copyfile(options['exam_file'], 'tmp.zip')
        fp = open('tmp.zip','rb')
        exam_file = File(fp)
        exam = Exam.objects.create(package=exam_file)
        exam.package.save(f'loaded-exam-{exam.pk}.zip', exam_file)
        exam.save()
        resource = Resource.objects.create(exam = exam)

        with open(options['attempts_file']) as f:
            data = json.load(f)

        print("GO")
        with transaction.atomic():
            for i,adata in enumerate(data['attempts']):
                user = users[adata['user']['username']]
                print(adata['attempt'], f'{i+1}/{len(data["attempts"])}')
                
                attempt = Attempt.objects.create(
                    resource=resource,
                    exam=resource.exam,
                    user=user,
                    start_time=tt(adata['start_time']),
                    end_time=tt(adata['end_time']),
                    completion_status=adata['completion_status'],
                    scaled_score=adata['scaled_score']
                )

                aqs = [
                    AttemptQuestionScore(
                        attempt=attempt,
                        number=qdata['question'],
                        raw_score=qdata['raw_score'],
                        max_score=qdata['max_score'],
                        scaled_score=qdata['scaled_score'],
                        completion_status=qdata['completion_status']
                    )
                    for qdata in adata['scores']
                ]

                AttemptQuestionScore.objects.bulk_create(aqs)

                scorms = [
                    ScormElement(
                        attempt=attempt,
                        key=key,
                        value=edata['value'],
                        time=tt(edata['time']),
                        counter=0
                    )
                    for key,edata in adata['scorm']['current'].items()
                ]

                ScormElement.objects.bulk_create(scorms)

        os.unlink('tmp.zip')
        print(f"The resource is at {resource.get_absolute_url()}")
