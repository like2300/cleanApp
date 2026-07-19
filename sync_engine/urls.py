from django.urls import path
from . import views

urlpatterns = [
    path('manual-sync/', views.manual_sync, name='manual_sync'),
    path('push/', views.push_to_cloud, name='push_to_cloud'),
    path('pull/', views.pull_from_cloud, name='pull_from_cloud'),
    path('force-pull/', views.force_pull_from_cloud, name='force_pull_from_cloud'),
    path('reconnect/', views.reconnect_cloud, name='reconnect_cloud'),
]
