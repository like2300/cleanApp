from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('login-redirect/', views.custom_login_redirect, name='login_redirect'),
    path('client/login/', views.client_login, name='client_login'),
    path('client/dashboard/', views.client_dashboard, name='client_dashboard'),
    path('client/change-plan/', views.change_subscription_plan, name='change_plan'),
    path('client/invoices/', views.client_invoice_list, name='client_invoice_list'),
    path('settings/', views.company_settings_edit, name='company_settings_edit'),
    
    # User Management
    path('users/', views.user_list, name='user_list'),
    path('users/create/', views.user_create, name='user_create'),
    path('users/<int:pk>/update/', views.user_update, name='user_update'),
    path('users/<int:pk>/delete/', views.user_delete, name='user_delete'),
    path('users/<int:pk>/toggle-active/', views.user_toggle_active, name='user_toggle_active'),
    path('users/<int:pk>/password-reset/', views.user_password_reset, name='user_password_reset'),
]
