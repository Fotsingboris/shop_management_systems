"""Vues des tableaux de bord (EF-12)."""
from __future__ import annotations

from django.contrib import messages

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView, UpdateView
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from general.mixins import AgenceScopedMixin

from general.forms import ParametresEntrepriseForm
from general.models import ParametresEntreprise

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
    

class ParametresEntrepriseUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Édition des paramètres de l'entreprise, singleton (EF-10.1). Réservé à l'Admin.
 
    ``get_object`` ignore tout pk d'URL et renvoie toujours l'unique
    instance via ``ParametresEntreprise.load()`` : il n'y a rien d'autre à
    éditer qu'elle (EF-11.3, appliqué ici côté vue en plus de l'admin).
    """
 
    model = ParametresEntreprise
    form_class = ParametresEntrepriseForm
    template_name = "dashboard/pages/general/parametres.html"
    success_url = reverse_lazy("general:parametres")
 
    def test_func(self) -> bool:
        return getattr(self.request.user, "is_admin", False)
 
    def get_object(self, queryset=None) -> ParametresEntreprise:
        return ParametresEntreprise.load()
 
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _("Paramètres de l'entreprise mis à jour."))
        return response