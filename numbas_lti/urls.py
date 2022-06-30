from django.urls import path
from django.contrib import auth

from . import views
urlpatterns = [
    path('', views.entry.index, name='index'),
    path('lti_entry', views.entry.lti_entry, name='lti_entry'),
    path('lockdown_launch', views.entry.lockdown_launch, name='lockdown_launch'),
    path('check_cookie_entry', views.entry.check_cookie_entry, name='check_cookie_entry'),
    path('set_cookie_entry', views.entry.set_cookie_entry, name='set_cookie_entry'),

    path('login', auth.views.LoginView.as_view(), name='login'),

    path('create-superuser', views.admin.CreateSuperuserView.as_view(), name='create_superuser'),

    path('dashboard', views.admin.DashboardView.as_view(), name='global_dashboard'),
    path('user-info/<int:pk>', views.admin.GlobalUserInfoView.as_view(), name='global_user_info'),

    path('search-autocomplete', views.search.search_autocomplete, name='search_autocomplete'),
    path('global-search', views.search.global_search, name='global_search'),

    path('resource/<int:pk>/create_exam', views.resource.CreateExamView.as_view(), name='create_exam'),
    path('exam/<int:pk>/run', views.resource.RunExamView.as_view(), name='run_exam'),

    path('resource/<int:pk>', views.resource.DashboardView.as_view(), name='resource_dashboard'),
    path('resource/<int:pk>/student_progress', views.resource.StudentProgressView.as_view(), name='student_progress'),
    path('resource/<int:pk>/discount_parts', views.resource.DiscountPartsView.as_view(), name='discount_parts'),
    path('resource/<int:pk>/validate_receipt', views.resource.ValidateReceiptView.as_view(), name='validate_receipt'),
    path('resource/<int:pk>/attempts', views.resource.AllAttemptsView.as_view(), name='manage_attempts'),
    path('resource/<int:pk>/reports', views.resource.FileReportsListView.as_view(), name='resource_reports'),
    path('resource/<int:pk>/stats', views.resource.StatsView.as_view(), name='resource_stats'),
    path('resource/<int:pk>/remark', views.resource.RemarkView.as_view(), name='resource_remark'),
    path('resource/<int:pk>/remark/iframe', views.resource.RemarkIframeView.as_view(), name='resource_remark_iframe'),
    path('resource/<int:pk>/remark/attempt_data', views.resource.RemarkGetAttemptDataView.as_view(), name='resource_remark_attempt_data'),
    path('resource/<int:pk>/remark/save_data', views.resource.RemarkSaveChangedDataView.as_view(), name='resource_remark_save_data'),
    path('resource/<int:pk>/settings', views.resource.ResourceSettingsView.as_view(), name='resource_settings'),
    path('resource/<int:pk>/replace', views.resource.ReplaceExamView.as_view(), name='replace_exam'),
    path('resource/<int:pk>/restore_exam', views.resource.RestoreExamView.as_view(), name='restore_exam'),
    path('resource/<int:pk>/use_current_version', views.resource.AttemptsUseCurrentVersionView.as_view(), name='use_current_version'),
    path('resource/<int:pk>/report_scores', views.resource.ReportAllScoresView.as_view(), name='report_scores'),
    path('resource/<int:pk>/scores.csv', views.resource.ScoresCSV.as_view(), name='scores_csv'),
    path('resource/<int:pk>/attempts.csv', views.resource.AttemptsCSV.as_view(), name='attempts_csv'),
    path('resource/<int:pk>/attempts.json', views.resource.JSONDumpView.as_view(), name='resource_json_dump'),
    path('resource/<int:resource_id>/grant_access_token/<int:user_id>', views.resource.grant_access_token, name='grant_access_token'),
    path('resource/<int:resource_id>/remove_access_token/<int:user_id>', views.resource.remove_access_token, name='remove_access_token'),
    path('resource/<int:resource_id>/access_changes', views.resource.AccessChangesView.as_view(), name='resource_access_changes'),
    path('resource/<int:resource_id>/access_change/create', views.resource.CreateAccessChangeView.as_view(), name='create_access_change'),
    path('access_change/<int:pk>', views.resource.UpdateAccessChangeView.as_view(), name='update_access_change'),
    path('access_change/<int:pk>/delete', views.resource.DeleteAccessChangeView.as_view(), name='delete_access_change'),

    path('attempt/<int:pk>/remark_parts', views.attempt.RemarkPartsView.as_view(), name='remark_parts'),
    path('attempt/<int:pk>/scorm-listing', views.attempt.AttemptSCORMListing.as_view(), name='attempt_scorm_listing'),
    path('attempt/<int:pk>/timeline', views.attempt.AttemptTimelineView.as_view(), name='attempt_timeline'),
    path('attempt/<int:pk>/delete', views.attempt.DeleteAttemptView.as_view(), name='delete_attempt'),
    path('attempt/<int:pk>/reopen', views.attempt.ReopenAttemptView.as_view(), name='reopen_attempt'),
    path('attempt/<int:pk>/scorm_data_fallback', views.attempt.scorm_data_fallback, name='attempt_scorm_data_fallback'),
    path('attempt/<int:pk>/data.json', views.attempt.JSONDumpView.as_view(), name='attempt_json_dump'),

    path('report-process/<int:pk>/dismiss', views.resource.DismissReportProcessView.as_view(), name='dismiss_report_process'),

    path('show_attempts', views.attempt.ShowAttemptsView.as_view(), name='show_attempts'),
    path('new_attempt', views.attempt.new_attempt, name='new_attempt'),
    path('run_attempt/<int:pk>', views.attempt.RunAttemptView.as_view(), name='run_attempt'),

    path('no-websockets', views.entry.no_websockets, name='no_websockets'),
    path('not-authorized', views.entry.not_authorized, name='not_authorized'),

    path('consumers', views.consumer.ListConsumersView.as_view(), name='list_consumers'),
    path('consumers/create', views.consumer.CreateConsumerView.as_view(), name='create_consumer'),
    path('consumers/<int:pk>', views.consumer.ManageConsumerView.as_view(), name='view_consumer'),
    path('consumers/<int:pk>/time-periods', views.consumer.ManageTimePeriodsView.as_view(), name='consumer_manage_time_periods'),
    path('consumers/<int:pk>/delete', views.consumer.DeleteConsumerView.as_view(), name='delete_consumer'),

    path('time-period/<int:pk>/delete', views.consumer.DeleteTimePeriodView.as_view(), name='delete_consumer_time_period'),

    path('contexts/<int:pk>', views.context.ManageContextView.as_view(), name='view_context'),
    path('contexts/<int:pk>/delete', views.context.DeleteContextView.as_view(), name='delete_context'),

    path('editorlinks', views.editorlink.ListEditorLinksView.as_view(), name='list_editorlinks'),
    path('editorlinks/create', views.editorlink.CreateEditorLinkView.as_view(), name='create_editorlink'),
    path('editorlink/<int:pk>/edit', views.editorlink.UpdateEditorLinkView.as_view(), name='edit_editorlink'),
    path('editorlink/<int:pk>/delete', views.editorlink.DeleteEditorLinkView.as_view(), name='delete_editorlink'),

    path('config.xml', views.entry.config_xml, name='config_xml'),

    path('stress', views.stress.ListStressTestsView.as_view(), name='list_stresstests'),
    path('stress/create', views.stress.create_stress_test, name='create_stresstest'),
    path('stress/<int:pk>/view', views.stress.StressTestView.as_view(), name='view_stresstest'),
    path('stress/<int:pk>/new-attempt', views.stress.NewAttemptView.as_view(), name='new_stresstest_attempt'),
    path('stress/<int:pk>/wipe', views.stress.WipeDataView.as_view(), name='wipe_stresstest'),
    path('stress/<int:pk>/delete', views.stress.DeleteStressTestView.as_view(), name='delete_stresstest'),
]
