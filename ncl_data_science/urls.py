from django.urls import path, include
from django.contrib import auth

from . import views

app_name = 'ncl_data_science'

urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path('case-studies', views.CaseStudiesView.as_view(), name='case_studies'),
    path('by-topic', views.TopicsView.as_view(), name='topics'),
    path('topic/<int:pk>', views.TopicView.as_view(), name='topic'),
]
