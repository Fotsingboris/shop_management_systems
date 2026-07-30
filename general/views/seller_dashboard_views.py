
# seller dashboard
from django.views import View
from django.shortcuts import render


class SellerDashboard(View):
    template = 'dashboard/pages/seller/dashboard/index.html'
    def get(self, request):
        return render(request, template_name=self.template)