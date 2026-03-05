from django_auth_lti.patch_reverse import reverse
from django.shortcuts import render
from django.http import JsonResponse
from django.views import generic
from django.views.decorators.csrf import csrf_exempt
import uuid
from numbas_lti.models import Attempt

from .models import StudentFile

@csrf_exempt
def upload_file(request):
    attempt_pk = request.POST.get('attempt')
    part = request.POST.get('part')
    attempt = Attempt.objects.get(pk=attempt_pk)
    files = request.FILES.getlist('file')
    ofiles = []
    for file in files:
        sf = StudentFile.objects.create(attempt=attempt, file=file, part=part)
        url = request.build_absolute_uri(sf.file.url)
        ofiles.append({'name': file.name, 'size': file.size, 'url': url, 'delete_url': reverse('delete_student_file', args=(sf.pk,))})
    return JsonResponse({'files': ofiles, })


class DeleteFileView(generic.edit.DeleteView):
    model = StudentFile
    def form_valid(self, form):
        self.object.file.delete()
        self.object.delete()
        return JsonResponse({'deleted': self.object.pk,})


class TestView(generic.TemplateView):
    template_name = 'student_files/test.html'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['files'] = StudentFile.objects.all()
        return context
