"""Vues des tableaux de bord (EF-12)."""
from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView

from general.mixins import AgenceScopedMixin


class AgenceDashboardView(LoginRequiredMixin, AgenceScopedMixin, TemplateView):
    """Tableau de bord d'une agence précise : /agences/<slug>/dashboard/.

    Accessible au Responsable/Caissier de cette agence, et à tout Admin qui
    consulte cette agence en particulier (EF-9.2, EF-12.4). ``self.agence``
    est posé par AgenceScopedMixin.dispatch() avant même que get() ne
    s'exécute.
    """

    template_name = "dashboard/pages/general/dashboard_home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # TODO: remplacer par les vraies agrégations, filtrées par self.agence,
        # ex. context["ventes_du_jour"] = Commande.objects.filter(agence=self.agence, ...)
        return context


class AdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Tableau de bord global, toutes agences confondues (EF-9.2, EF-12.4)."""

    template_name = "dashboard/pages/general/dashboard_home.html"

    def test_func(self) -> bool:
        return getattr(self.request.user, "is_admin", False)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["agence"] = None
        return context