from django.urls import path
from . import views

urlpatterns = [
    path('reclamations/', views.reclamation_list, name='reclamation_list'),
    path('reclamations/<int:pk>/', views.reclamation_detail, name='reclamation_detail'),
    path('reclamations/nouvelle/', views.reclamation_create, name='reclamation_create'),
    path('api/unread/', views.get_unread_notifications, name='get_unread_notifications'),
    path('api/read/<int:pk>/', views.mark_notification_read, name='mark_notification_read'),
    path('api/public-reclamation/', views.public_reclamation, name='public_reclamation'),
]
