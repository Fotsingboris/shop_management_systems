
# admin dashboard
from django.views import View
from django.shortcuts import render


class ManagerDashboard(View):
    template = 'dashboard/pages/manager/dashboard/index.html'
    def get(self, request):
        return render(request, template_name=self.template)