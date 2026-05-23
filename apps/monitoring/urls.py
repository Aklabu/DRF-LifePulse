from django.urls import path
from . import views

urlpatterns = [
    path('check-in/', views.CheckInView.as_view(), name='check-in'),
    path('status/', views.MonitoringStatusView.as_view(), name='monitoring-status'),
]
