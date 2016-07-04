from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^lti_entry$', views.lti_entry, name='lti_entry'),
    url(r'^exam/create$', views.CreateExamView.as_view(), name='create_exam'),
    url(r'^exam/(?P<pk>\d+)/run$', views.RunExamView.as_view(), name='run_exam'),

    url(r'^resource/(?P<pk>\d+)$', views.DashboardView.as_view(), name='dashboard'),
    url(r'^resource/(?P<pk>\d+)/attempts$', views.AllAttemptsView.as_view(), name='manage_attempts'),
    url(r'^resource/(?P<pk>\d+)/settings$', views.ResourceSettingsView.as_view(), name='resource_settings'),
    url(r'^resource/(?P<pk>\d+)/replace$', views.ReplaceExamView.as_view(), name='replace_exam'),

    url(r'^resource/(?P<pk>\d+)/scores.csv$', views.ScoresCSV.as_view(), name='scores_csv'),
    url(r'^resource/(?P<pk>\d+)/attempts.csv$', views.AttemptsCSV.as_view(), name='attempts_csv'),

    url(r'grant_access_token/(?P<user_id>\d+)$', views.grant_access_token, name='grant_access_token'),
    url(r'remove_access_token/(?P<user_id>\d+)$', views.remove_access_token, name='remove_access_token'),

    url(r'^show_attempts$', views.ShowAttemptsView.as_view(), name='show_attempts'),
    url(r'^new_attempt$', views.new_attempt, name='new_attempt'),
    url(r'^run_attempt/(?P<pk>\d+)$', views.RunAttemptView.as_view(), name='run_attempt'),
]
