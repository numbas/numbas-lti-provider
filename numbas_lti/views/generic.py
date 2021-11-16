import csv
from django.contrib import messages
from django.core.files.base import ContentFile
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.template.loader import get_template
from django.utils.translation import ugettext_lazy as _
from datetime import datetime
from django.utils import timezone
from numbas_lti.models import FileReport
from pathlib import Path
import uuid

class EchoFile(object):
    def write(self,value):
        return value

class CreateFileReportView(object):
    http_method_names = ['post','options','put',]

    report_task = None
    
    def get_name(self):
        raise NotImplementedError()

    def get_resource(self):
        raise NotImplementedError()

    def get_filename(self):
        raise NotImplementedError()

    def get_task_kwargs(self):
        return {}

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        fr = FileReport(name=self.get_name(), created_by=self.request.user, resource=self.get_resource())
        filename = Path(self.get_filename())
        filename = '{stem}-{date}-{uuid}{suffix}'.format(
                stem = filename.stem,
                date = datetime.now().strftime('%Y-%d-%m-%H_%M_%S'),
                uuid = str(uuid.uuid4())[:8],
                suffix = filename.suffix
        )
        fr.outfile.save(filename, ContentFile(''))
        self.report_task(fr, **self.get_task_kwargs())
        template = get_template('numbas_lti/management/file_report_created.html')
        message = template.render({'report':fr})
        messages.add_message(self.request, messages.INFO, message)

        return HttpResponseRedirect(self.get_success_url())

class JSONView(object):
    def get_data(self):
        raise NotImplementedError()
    def get_filename(self):
        raise NotImplementedError()

    def render_to_response(self,context,**kwargs):
        response = JsonResponse(self.get_data())
        response['Content-Disposition'] = 'attachment; filename="{}"'.format(self.get_filename())
        return response
