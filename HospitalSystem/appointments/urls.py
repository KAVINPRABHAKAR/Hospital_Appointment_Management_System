from django.urls import path
from . import views

urlpatterns = [
     path('', views.dashboard, name='dashboard'),
    path('register/', views.register_patient, name='register_patient'),
    path('queues/', views.doctor_queues, name='doctor_queues'),
    path('consulted/<int:appointment_id>/', views.mark_consulted, name='mark_consulted'),
    path('search/', views.search_patient, name='search_patient'),
    path('analytics/', views.analytics_report, name='analytics_report'),
    path('export-pdf/', views.export_pdf, name='export_pdf'),
    path('analytics/departments/', views.department_analytics, name='dept_analytics'),
    path('analytics/export/', views.export_pdf, name='export_pdf'),
]






