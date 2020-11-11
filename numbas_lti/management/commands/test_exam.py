from django.core.management.base import BaseCommand
import os
import json
import subprocess
import datetime
from django.utils.timezone import now

from numbas_lti.models import Exam, Resource
from numbas_lti.test_exam import test_exam, ExamTestException

class Command(BaseCommand):
    help = 'Test an exam package'

    def add_arguments(self, parser):
        parser.add_argument('exam_pk',nargs='?',type=int)
        parser.add_argument('--resource',type=int,dest='resource', help='The ID of a resource whose current exam package should be tested')

    def handle(self, *args, **options):

        if options.get('resource'):
            exam = Resource.objects.get(pk=options['resource']).exam
        elif options.get('exam_pk'):
            exam_pk = options['exam_pk']
            exam = Exam.objects.get(pk=exam_pk)
        else:
            raise Exception("You must give either an exam ID or a resource ID.")

        print("Testing exam {}, \"{}\".".format(exam.pk,exam.title))
        try:
            result = test_exam(exam)
            print("This exam passed all the tests.")
        except ExamTestException as e:
            print(e)

