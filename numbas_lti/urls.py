from django.conf.urls import url
from django.contrib import auth

from . import views
urlpatterns = [
    url(r'^$', views.entry.index, name='index'),
    url(r'^lti_entry$', views.entry.lti_entry, name='lti_entry'),

    url(r'^login$', auth.views.LoginView.as_view(), name='login'),

    url(r'^create-superuser$', views.admin.CreateSuperuserView.as_view(), name='create_superuser'),

    url(r'^resource/(?P<pk>\d+)/create_exam$', views.resource.CreateExamView.as_view(), name='create_exam'),
    url(r'^exam/(?P<pk>\d+)/run$', views.resource.RunExamView.as_view(), name='run_exam'),

    url(r'^resource/(?P<pk>\d+)$', views.resource.DashboardView.as_view(), name='dashboard'),
    url(r'^resource/(?P<pk>\d+)/discount_parts$', views.resource.DiscountPartsView.as_view(), name='discount_parts'),
    url(r'^resource/(?P<pk>\d+)/discount_part$', views.resource.DiscountPartView.as_view(), name='discount_part'),
    url(r'^discount_part/(?P<pk>\d+)/update$', views.resource.DiscountPartUpdateView.as_view(), name='discount_part_update'),
    url(r'^discount_part/(?P<pk>\d+)/delete$', views.resource.DiscountPartDeleteView.as_view(), name='discount_part_delete'),
    url(r'^resource/(?P<pk>\d+)/remark_part$', views.attempt.RemarkPartView.as_view(), name='remark_part'),
    url(r'^remark_part/(?P<pk>\d+)/update$', views.attempt.RemarkPartUpdateView.as_view(), name='remark_part_update'),
    url(r'^remark_part/(?P<pk>\d+)/delete$', views.attempt.RemarkPartDeleteView.as_view(), name='remark_part_delete'),
    url(r'^resource/(?P<pk>\d+)/attempts$', views.resource.AllAttemptsView.as_view(), name='manage_attempts'),
    url(r'^resource/(?P<pk>\d+)/stats$', views.resource.StatsView.as_view(), name='resource_stats'),
    url(r'^resource/(?P<pk>\d+)/settings$', views.resource.ResourceSettingsView.as_view(), name='resource_settings'),
    url(r'^resource/(?P<pk>\d+)/replace$', views.resource.ReplaceExamView.as_view(), name='replace_exam'),
    url(r'^resource/(?P<pk>\d+)/report_scores$', views.resource.ReportAllScoresView.as_view(), name='report_scores'),
    url(r'^resource/(?P<pk>\d+)/scores.csv$', views.resource.ScoresCSV.as_view(), name='scores_csv'),
    url(r'^resource/(?P<pk>\d+)/attempts.csv$', views.resource.AttemptsCSV.as_view(), name='attempts_csv'),
    url(r'^resource/(?P<resource_id>\d+)/grant_access_token/(?P<user_id>\d+)$', views.resource.grant_access_token, name='grant_access_token'),
    url(r'^resource/(?P<resource_id>\d+)/remove_access_token/(?P<user_id>\d+)$', views.resource.remove_access_token, name='remove_access_token'),

    url(r'^attempt/(?P<pk>\d+)/remark_parts$', views.attempt.RemarkPartsView.as_view(), name='remark_parts'),
    url(r'^attempt/(?P<pk>\d+)/scorm-listing$', views.attempt.AttemptSCORMListing.as_view(), name='attempt_scorm_listing'),
    url(r'^attempt/(?P<pk>\d+)/delete$', views.attempt.DeleteAttemptView.as_view(), name='delete_attempt'),
    url(r'^attempt/(?P<pk>\d+)/reopen$', views.attempt.ReopenAttemptView.as_view(), name='reopen_attempt'),
    url(r'^attempt/(?P<pk>\d+)/scorm_data_fallback$', views.attempt.scorm_data_fallback, name='attempt_scorm_data_fallback'),

    url(r'report-process/(?P<pk>\d+)/dismiss$', views.resource.DismissReportProcessView.as_view(), name='dismiss_report_process'),

    url(r'^show_attempts$', views.attempt.ShowAttemptsView.as_view(), name='show_attempts'),
    url(r'^new_attempt$', views.attempt.new_attempt, name='new_attempt'),
    url(r'^run_attempt/(?P<pk>\d+)$', views.attempt.RunAttemptView.as_view(), name='run_attempt'),

    url(r'^no-websockets$', views.entry.no_websockets, name='no_websockets'),
    url(r'^not-authorized$', views.entry.not_authorized, name='not_authorized'),

    url(r'^consumers$', views.consumer.ListConsumersView.as_view(), name='list_consumers'),
    url(r'^consumers/create$', views.consumer.CreateConsumerView.as_view(), name='create_consumer'),
    url(r'^consumers/(?P<pk>\d+)$', views.consumer.ManageConsumerView.as_view(), name='view_consumer'),
    url(r'^consumers/(?P<pk>\d+)/time-periods$', views.consumer.ManageTimePeriodsView.as_view(), name='consumer_manage_time_periods'),
    url(r'^consumers/(?P<pk>\d+)/delete$', views.consumer.DeleteConsumerView.as_view(), name='delete_consumer'),

    url(r'^time-period/(?P<pk>\d+)/delete$', views.consumer.DeleteTimePeriodView.as_view(), name='delete_consumer_time_period'),

    url(r'^contexts/(?P<pk>\d+)$', views.context.ManageContextView.as_view(), name='view_context'),
    url(r'^contexts/(?P<pk>\d+)/delete$', views.context.DeleteContextView.as_view(), name='delete_context'),

    url(r'^editorlinks$', views.editorlink.ListEditorLinksView.as_view(), name='list_editorlinks'),
    url(r'^editorlinks/create$', views.editorlink.CreateEditorLinkView.as_view(), name='create_editorlink'),
    url(r'^editorlink/(?P<pk>\d+)/edit$', views.editorlink.UpdateEditorLinkView.as_view(), name='edit_editorlink'),
    url(r'^editorlink/(?P<pk>\d+)/delete$', views.editorlink.DeleteEditorLinkView.as_view(), name='delete_editorlink'),

    url(r'^config.xml$', views.entry.config_xml, name='config_xml'),

    url(r'^stress$', views.stress.ListStressTestsView.as_view(), name='list_stresstests'),
    url(r'^stress/create$', views.stress.create_stress_test, name='create_stresstest'),
    url(r'^stress/(?P<pk>\d+)/view$', views.stress.StressTestView.as_view(), name='view_stresstest'),
    url(r'^stress/(?P<pk>\d+)/new-attempt$', views.stress.NewAttemptView.as_view(), name='new_stresstest_attempt'),
    url(r'^stress/(?P<pk>\d+)/wipe$', views.stress.WipeDataView.as_view(), name='wipe_stresstest'),
    url(r'^stress/(?P<pk>\d+)/delete$', views.stress.DeleteStressTestView.as_view(), name='delete_stresstest'),
]
