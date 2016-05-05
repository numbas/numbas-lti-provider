from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^lti_entry$', views.lti_entry, name='lti_entry'),
    url(r'^exam/create$', views.CreateExamView.as_view(), name='create_exam'),
    url(r'^exam/(?P<pk>\d+)/run$', views.RunExamView.as_view(), name='run_exam'),

    url(r'^resource/(?P<pk>\d+)$', views.ManageResourceView.as_view(), name='manage_resource'),
    url(r'^resource/(?P<pk>\d+)/settings$', views.ResourceSettingsView.as_view(), name='resource_settings'),

    url(r'grant_access_token/(?P<user_id>\d+)$', views.grant_access_token, name='grant_access_token'),

    url(r'^show_attempts$', views.ShowAttemptsView.as_view(), name='show_attempts'),
    url(r'^new_attempt$', views.new_attempt, name='new_attempt'),
    url(r'^run_attempt/(?P<pk>\d+)$', views.RunAttemptView.as_view(), name='run_attempt'),
]
