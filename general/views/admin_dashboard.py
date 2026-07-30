
# admin dashboard
from django.views import View
from django.shortcuts import render


class AdminDashboard(View):
    template = 'dashboard/pages/admin/dashboard/index.html'
    def get(self, request):
        return render(request, template_name=self.template)