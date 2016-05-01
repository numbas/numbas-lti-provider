from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^view2$', views.view2, name='view2'),
    url(r'^exam/create$', views.CreateExamView.as_view(), name='create_exam'),
    url(r'^exam/(?P<pk>\d+)/run$', views.RunExamView.as_view(), name='run_exam'),
    url(r'^resource/(?P<pk>\d+)$', views.ManageResourceView.as_view(), name='manage_resource'),
]
