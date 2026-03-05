from django.urls import path, include
from django.views.decorators.csrf import csrf_exempt

from . import views

urlpatterns = [
    path('upload', views.upload_file, name='upload_student_file'),
    path('delete/<pk>', csrf_exempt(views.DeleteFileView.as_view()), name='delete_student_file'),
    path('test', views.TestView.as_view(), name='test_student_file'),
]
