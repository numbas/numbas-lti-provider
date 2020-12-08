from django.conf import settings
import json
import os
from pathlib import Path
import shutil
import subprocess
import datetime
import tempfile

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

def run_package(extracted_path,command='test',stdin='',options={}):
    if not hasattr(settings,'NUMBAS_TESTING_FRAMEWORK_PATH'):
        raise ExamTestException("The NUMBAS_TESTING_FRAMEWORK_PATH setting has not been set.")

    root = Path(extracted_path)
    manifest_path = root / 'numbas-manifest.json'
    if not manifest_path.exists():
        raise ExamTestException("This package doesn't contain a numbas-manifest.json file.")

    with open(str(manifest_path)) as f:
        manifest = json.loads(f.read())

    features = manifest.get('features',{})
    if not features.get('run_headless'):
        raise ExamTestException("This package can not run outside of a browser.")

    option_args = []
    for k,v in options.items():
        if isinstance(v,bool):
            if v:
                option_args += ['--'+k]
        elif isinstance(v,list):
            if len(v)>0:
                option_args += ['--'+k,' '.join(v)]
        else:
            option_args += ['--'+k,v]

    command = [
        str(Path(settings.NUMBAS_TESTING_FRAMEWORK_PATH) / 'test_exam'),
        str(Path(os.getcwd()) / extracted_path),
        command
    ] + option_args

    with tempfile.TemporaryFile() as stdoutf:
        with tempfile.TemporaryFile() as stderrf:
            process = subprocess.Popen(command, stdout=stdoutf, stdin=subprocess.PIPE, stderr=stderrf)
            print("Remarking")
            process.communicate(input=stdin.encode('utf-8'))
            print("Finished remarking")
            stdoutf.seek(0)
            stdout = stdoutf.read().decode('utf-8')
            stderrf.seek(0)
            stderr = stderrf.read().decode('utf-8')
            code = process.poll()
    if code != 0:
        raise ExamTestException('There was an error while running the exam.', stdout=stdout, stderr=stderr, code=code)

    try:
        result = json.loads(stdout.strip())
    except json.JSONDecodeError as e:
        print("STDOUT:",stdout)
        print("STDERR:",stderr)
        raise ExamTestException('There was an error decoding the results of the test.', stdout=stdout, stderr=stderr)

    if not result.get('success',False):
        raise ExamTestException(result.get('message','The exam did not work as expected.'),stdout=stdout,stderr=stderr)

    if stderr:
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

def remark_attempts(exam, attempts, apply_unsubmitted_answers=False, reevaluate_variables=[]):
    cmis = []
    print("Gathering attempt data for {} attempts".format(attempts.count()))
    for a in attempts:
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
    options = {
        'unsubmitted': apply_unsubmitted_answers,
        'reevaluate_variables': reevaluate_variables,
    }
    result = run_package(exam.extracted_path, stdin=json.dumps(cmis), command='remark',options = options)
    return result
