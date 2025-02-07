from .views import lti_13 as views, resource as resource_views
from django.urls import path

app_name = 'lti'

urlpatterns = [
    path(r'register/', views.RegisterView.as_view(), name='register'),
    path(r'register/dynamic/new-token/', views.CreateRegistrationTokenView.as_view(), name='new_dynamic_registration_token'),
    path(r'register/dynamic/<uuid:pk>/view/', views.RegistrationTokenView.as_view(), name='view_dynamic_registration_token'),
    path(r'register/dynamic/<uuid:pk>/use/', views.UseRegistrationTokenView.as_view(), name='use_dynamic_registration_token'),
    path(r'register/canvas', views.CanvasRegistrationView.as_view(), name='register_canvas'),
    path(r'register/blackboard', views.BlackboardRegistrationView.as_view(), name='register_blackboard'),
    path(r'register/generic', views.GenericRegistrationView.as_view(), name='register_generic'),
    path(r'register/canvas_config.json', views.canvas_config_json, name='canvas_config_json'),

    path(r'login/', views.LoginView.as_view(), name='login'),

    path(r'jwks/', views.JWKSView.as_view(), name='jwks'),

    path(r'launch/', views.LaunchView.as_view(), name='launch'),
    path(r'launch/teacher/', views.TeacherLaunchView.as_view(), name='teacher_launch'),
    path(r'launch/student/', views.StudentLaunchView.as_view(), name='student_launch'),

    path(r'deep-link/', views.DeepLinkView.as_view(), name='deep_link'),
    path(r'deep-link/use-resource/', views.DeepLinkUseResourceView.as_view(), name='deep_link_use_resource'),
    path(r'deep-link/create-resource/', views.DeepLinkCreateResourceView.as_view(), name='deep_link_create_resource'),
    path(r'deep-link/use-context=summary/', views.DeepLinkUseContextSummaryView.as_view(), name='deep_link_use_context_summary'),
    path(r'deep-link/create-context-summary/', views.DeepLinkCreateContextSummaryView.as_view(), name='deep_link_create_context_summary'),
]
