from .views import lti_13 as views, resource as resource_views
from django.urls import path

app_name = 'lti'

urlpatterns = [
    path(r'register/', views.RegisterView.as_view(), name='register'),
    path(r'register/dynamic/', views.register_dynamic, name='dynamic_registration'),
    path(r'register/canvas_config.json', views.canvas_config_json, name='canvas_config_json'),

    path(r'login/', views.LoginView.as_view(), name='login'),

    path(r'jwks/', views.JWKSView.as_view(), name='jwks'),

    path(r'launch/', views.LaunchView.as_view(), name='launch'),
    path(r'launch/teacher/', views.TeacherLaunchView.as_view(), name='teacher_launch'),
    path(r'launch/student/', views.StudentLaunchView.as_view(), name='student_launch'),

    path(r'deep-link/', views.DeepLinkView.as_view(), name='deep_link'),
    path(r'deep-link/use-resource/', views.DeepLinkUseResourceView.as_view(), name='deep_link_use_resource'),
    path(r'deep-link/create-resource/', views.DeepLinkCreateResourceView.as_view(), name='deep_link_create_resource'),
]
