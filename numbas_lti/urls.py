from django.conf.urls import url
from django.contrib import auth

from . import views

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^lti_entry$', views.lti_entry, name='lti_entry'),

    url(r'^login$', auth.views.login, name='login'),

    url(r'^create-superuser$', views.CreateSuperuserView.as_view(), name='create_superuser'),

    url(r'^resource/(?P<pk>\d+)/create_exam$', views.CreateExamView.as_view(), name='create_exam'),
    url(r'^exam/(?P<pk>\d+)/run$', views.RunExamView.as_view(), name='run_exam'),

    url(r'^resource/(?P<pk>\d+)$', views.DashboardView.as_view(), name='dashboard'),
    url(r'^resource/(?P<pk>\d+)/discount_parts$', views.DiscountPartsView.as_view(), name='discount_parts'),
    url(r'^resource/(?P<pk>\d+)/discount_part$', views.DiscountPartView.as_view(), name='discount_part'),
    url(r'^discount_part/(?P<pk>\d+)/update$', views.DiscountPartUpdateView.as_view(), name='discount_part_update'),
    url(r'^discount_part/(?P<pk>\d+)/delete$', views.DiscountPartDeleteView.as_view(), name='discount_part_delete'),
    url(r'^resource/(?P<pk>\d+)/remark_part$', views.RemarkPartView.as_view(), name='remark_part'),
    url(r'^remark_part/(?P<pk>\d+)/update$', views.RemarkPartUpdateView.as_view(), name='remark_part_update'),
    url(r'^remark_part/(?P<pk>\d+)/delete$', views.RemarkPartDeleteView.as_view(), name='remark_part_delete'),
    url(r'^resource/(?P<pk>\d+)/attempts$', views.AllAttemptsView.as_view(), name='manage_attempts'),
    url(r'^resource/(?P<pk>\d+)/settings$', views.ResourceSettingsView.as_view(), name='resource_settings'),
    url(r'^resource/(?P<pk>\d+)/replace$', views.ReplaceExamView.as_view(), name='replace_exam'),
    url(r'^resource/(?P<pk>\d+)/report_scores$', views.ReportAllScoresView.as_view(), name='report_scores'),
    url(r'^resource/(?P<pk>\d+)/scores.csv$', views.ScoresCSV.as_view(), name='scores_csv'),
    url(r'^resource/(?P<pk>\d+)/attempts.csv$', views.AttemptsCSV.as_view(), name='attempts_csv'),

    url(r'^attempt/(?P<pk>\d+)/remark_parts$', views.RemarkPartsView.as_view(), name='remark_parts'),
    url(r'^attempt/(?P<pk>\d+)/scorm-listing$', views.AttemptSCORMListing.as_view(), name='attempt_scorm_listing'),
    url(r'^attempt/(?P<pk>\d+)/delete$', views.DeleteAttemptView.as_view(), name='delete_attempt'),
    url(r'^attempt/(?P<pk>\d+)/reopen$', views.ReopenAttemptView.as_view(), name='reopen_attempt'),
    url(r'^attempt/(?P<pk>\d+)/scorm_data_fallback$', views.scorm_data_fallback, name='attempt_scorm_data_fallback'),

    url(r'grant_access_token/(?P<user_id>\d+)$', views.grant_access_token, name='grant_access_token'),
    url(r'remove_access_token/(?P<user_id>\d+)$', views.remove_access_token, name='remove_access_token'),

    url(r'report-process/(?P<pk>\d+)/dismiss$', views.DismissReportProcessView.as_view(), name='dismiss_report_process'),

    url(r'^show_attempts$', views.ShowAttemptsView.as_view(), name='show_attempts'),
    url(r'^new_attempt$', views.new_attempt, name='new_attempt'),
    url(r'^run_attempt/(?P<pk>\d+)$', views.RunAttemptView.as_view(), name='run_attempt'),

    url(r'^no-websockets$', views.no_websockets, name='no_websockets'),
    url(r'^not-authorized$', views.not_authorized, name='not_authorized'),

    url(r'^consumers$', views.ListConsumersView.as_view(), name='list_consumers'),
    url(r'^consumers/create$', views.CreateConsumerView.as_view(), name='create_consumer'),
    url(r'^consumers/(?P<pk>\d+)$', views.ManageConsumerView.as_view(), name='view_consumer'),
    url(r'^consumers/(?P<pk>\d+)/delete$', views.DeleteConsumerView.as_view(), name='delete_consumer'),

    url(r'^editorlinks$', views.ListEditorLinksView.as_view(), name='list_editorlinks'),
    url(r'^editorlinks/create$', views.CreateEditorLinkView.as_view(), name='create_editorlink'),
    url(r'^editorlink/(?P<pk>\d+)/edit$', views.UpdateEditorLinkView.as_view(), name='edit_editorlink'),
    url(r'^editorlink/(?P<pk>\d+)/delete$', views.DeleteEditorLinkView.as_view(), name='delete_editorlink'),

	url(r'^config.xml$', views.config_xml, name='config_xml'),
]
