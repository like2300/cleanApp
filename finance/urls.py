from django.urls import path

from . import views

urlpatterns = [
    path("invoices/", views.invoice_list, name="invoice_list"),
    path("invoices/add/", views.invoice_create, name="invoice_create_manual"),
    path(
        "invoices/create/<int:subscription_id>/",
        views.create_invoice_from_subscription,
        name="invoice_create",
    ),
    path("invoices/pay-initiate/", views.initiate_payment, name="initiate_payment"),
    path(
        "invoices/pay-initiate/<int:invoice_id>/",
        views.initiate_payment,
        name="initiate_payment_specific",
    ),
    path(
        "invoices/export-my/", views.export_my_invoices_excel, name="export_my_invoices"
    ),
    path("invoices/<int:invoice_id>/pay/", views.payment_create, name="payment_create"),
    path(
        "payments/<int:payment_id>/validate/",
        views.payment_validate,
        name="payment_validate",
    ),
    path("expenses/", views.expense_list, name="expense_list"),
    path("expenses/add/", views.expense_create, name="expense_create"),
    path("expenses/<int:pk>/edit/", views.expense_edit, name="expense_edit"),
    path("expenses/<int:pk>/delete/", views.expense_delete, name="expense_delete"),
    path(
        "expenses/categories/add/",
        views.expense_category_create,
        name="expense_category_create",
    ),
    path(
        "expenses/categories/<int:pk>/edit/",
        views.expense_category_edit,
        name="expense_category_edit",
    ),
    path(
        "expenses/categories/<int:pk>/delete/",
        views.expense_category_delete,
        name="expense_category_delete",
    ),
    path("analytics/", views.analytics_dashboard, name="analytics_dashboard"),
]
