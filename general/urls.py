from django.urls import path

from general.views.admin_dashboard import AdminDashboard

app_name = 'general'
urlpatterns = [
    # admin dashboard
    path('admin/dashboard/', AdminDashboard.as_view(), name='admin_dashboard')
]