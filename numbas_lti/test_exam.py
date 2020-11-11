from django.conf import settings
import json
import os
from pathlib import Path
import shutil
import subprocess
import datetime

class ExamTestException(Exception):
    def __init__(self, message, stdout='', stderr='', code=0):
        super().__init__()
        self.message = message
        self.stdout = stdout
        self.stderr = stderr
        self.code = code

    def __str__(self):
        out = self.message
        if self.stdout:
            out += '\n\nSTDOUT:\n'+self.stdout
        if self.stderr:
            out += '\n\nSTDERR:\n'+self.stderr
        if self.code:
            out += '\n\nExit code: '+str(self.code)
        return out
    
    pass

def run_package(extracted_path,command='test',stdin=None):
    if not hasattr(settings,'NUMBAS_TESTING_FRAMEWORK_PATH'):
        raise ExamTestException("The NUMBAS_TESTING_FRAMEWORK_PATH setting has not been set.")

    root = Path(extracted_path)
    manifest_path = root / 'numbas-manifest.json'
    if not manifest_path.exists():
        raise ExamTestException("This package doesn't contain a numbas-manifest.json file.")

    with open(manifest_path) as f:
        manifest = json.loads(f.read())

    features = manifest.get('features',{})
    if not features.get('run_headless'):
        raise ExamTestException("This package can not run outside of a browser.")


    command = [
        Path(settings.NUMBAS_TESTING_FRAMEWORK_PATH) / 'test_exam',
        Path(os.getcwd()) / extracted_path,
        command
    ]

    process = subprocess.Popen(command, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE,encoding='utf-8')
    stdout, stderr = process.communicate(input=stdin)
    code = process.poll()
    if code != 0:
        raise ExamTestException('There was an error while running the exam.', stdout=stdout, stderr=stderr, code=code)

    try:
        result = json.loads(stdout.strip())
    except json.JSONDecodeError as e:
        print(stdout)
        print(stderr)
        raise ExamTestException('There was an error decoding the results of the test.', stdout=stdout, stderr=stderr)

    if not result.get('success',False):
        raise ExamTestException(result.get('message','The exam did not work as expected.'),stdout=stdout,stderr=stderr)

    print(stderr)
    return result

def test_package(extracted_path):
    run_package(extracted_path)
    return True


def test_exam(exam):
    return test_package(exam.extracted_path)

def test_zipfile(zipfile):
    path = Path(os.getcwd(), settings.MEDIA_ROOT) / 'test_zips'
    i = 0
    while (path / str(i)).exists():
        i += 1
    path = path / str(i)
    path.mkdir(parents=True, exist_ok=True)
    zipfile.extractall(path)
    try:
        result = test_package(path)
    finally:
        shutil.rmtree(path)
    return result

def remark_attempts(exam):
    cmis = []
    for a in exam.attempts.all():
        cmi = a.scorm_cmi()

        dynamic_cmi = {
            'cmi.mode': 'review',
            'cmi.entry': 'resume',
            'numbas.user_role': 'student',
        }
        etime = datetime.datetime.now().timestamp()
        dynamic_cmi = {k: {'value':v,'time':etime} for k,v in dynamic_cmi.items()}
        cmi.update(dynamic_cmi)
        cmis.append({'attempt_pk': a.pk, 'cmi': cmi})
    result = run_package(exam.extracted_path, stdin=json.dumps(cmis), command='remark')
    return result
