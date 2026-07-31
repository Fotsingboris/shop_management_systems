"""Vues des tableaux de bord (EF-12), des agences (EF-1) et des paramètres de l'entreprise (EF-10)."""
from __future__ import annotations

from typing import Any, Dict

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Q, QuerySet
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, ListView, UpdateView

from general.forms import AgenceForm
from general.models import Agence


class AdminRequiredMixin(UserPassesTestMixin):
    """Réservé à l'Admin (EF-1.1 : gestion des agences)."""

    def test_func(self) -> bool:
        return getattr(self.request.user, "is_admin", False)


class AgenceListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    """Liste paginée des agences, avec recherche (EF-1, EF-13.3).

    ``annotate`` (Count distinct) pour le nombre d'utilisateurs rattachés
    à chaque agence plutôt qu'une requête par ligne affichée (EF-13.1).
    """

    model = Agence
    template_name = "dashboard/pages/general/agency/agence_list.html"
    context_object_name = "agences"
    paginate_by = 20

    def get_queryset(self) -> QuerySet[Agence]:
        qs = Agence.objects.annotate(
            nombre_utilisateurs=Count("utilisateurs", distinct=True)
        ).order_by("nom")
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(Q(nom__icontains=q) | Q(adresse__icontains=q))
        return qs

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["q"] = self.request.GET.get("q", "")
        return context


class AgenceCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    """Création d'une agence (EF-1.1)."""

    model = Agence
    form_class = AgenceForm
    template_name = "dashboard/pages/general/agency/agence_form.html"
    success_url = reverse_lazy("general:agence_list")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _("Agence « %(nom)s » créée.") % {"nom": self.object.nom})
        return response


class AgenceUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    """Modification d'une agence existante (EF-1.1, EF-1.3 pour l'activation/désactivation).

    Réutilise ``AgenceForm`` et le même template que la création — voir
    ``agence_form.html`` pour la distinction création/édition via
    ``{% if object %}`` (le pk UUID d'Agence est déjà posé sur une
    instance non enregistrée, donc ``form.instance.pk`` ne peut pas servir
    à cette distinction, comme observé sur Categorie/Produit).
    """

    model = Agence
    form_class = AgenceForm
    template_name = "dashboard/pages/general/agency/agence_form.html"
    success_url = reverse_lazy("general:agence_list")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _("Agence « %(nom)s » mise à jour.") % {"nom": self.object.nom})
        return response

