from django.http import StreamingHttpResponse, JsonResponse
from django.shortcuts import render
from django.utils.translation import ugettext_lazy as _
import csv

class EchoFile(object):
    def write(self,value):
        return value

class CSVView(object):
    def get_rows(self):
        raise NotImplementedError()
    def get_filename(self):
        raise NotImplementedError()

    def render_to_response(self,context):
        buffer = EchoFile()
        writer = csv.writer(buffer)
        rows = self.get_rows()
        response = StreamingHttpResponse((writer.writerow(row) for row in rows),content_type="text/csv")
        response['Content-Disposition'] = 'attachment; filename="{}"'.format(self.get_filename())
        return response

class JSONView(object):
    def get_data(self):
        raise NotImplementedError()
    def get_filename(self):
        raise NotImplementedError()

    def render_to_response(self,context,**kwargs):
        response = JsonResponse(self.get_data())
        response['Content-Disposition'] = 'attachment; filename="{}"'.format(self.get_filename())
        return response
