"""Vues des tableaux de bord (EF-12).

Trois profils partagent DEUX vues seulement :

- ``AdminDashboardView`` (``dashboard_mode = "global"``) : Admin, toutes
  agences confondues.
- ``AgenceDashboardView`` (``self.agence`` posé par ``AgenceScopedMixin``) :
  se scinde elle-même en deux rendus selon le rôle du visiteur —
  ``dashboard_mode = "agence"`` pour un Responsable d'agence (ou un Admin
  qui vient consulter cette agence en particulier), et
  ``dashboard_mode = "caissier"`` pour un Caissier, qui ne doit voir QUE
  son propre historique (EF-9.4 : "limité ... à son historique"), jamais
  les ventes de ses collègues de la même agence.

Les trois templates partagent le même ``dashboard_home.html``, qui inclut
le partiel correspondant à ``dashboard_mode``. Le calcul des agrégations
est délégué à ``general/dashboard_services.py`` : cette vue ne fait
qu'orchestrer quelles fonctions appeler et avec quel périmètre.
"""
from __future__ import annotations

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView, UpdateView

from general.dashboard_services import (
    STATUTS_TRANSACTION,
    appliquer_periode,
    ca_par_agence,
    ca_par_agence_map,
    calculer_kpis_ventes,
    performance_caissiers,
    produits_stock_bas,
    resoudre_periode,
    serie_ca_dans_le_temps,
    stock_bas_par_agence_map,
    top_produits,
    valeur_stock,
    ventes_par_categorie,
    ventes_par_mode_paiement,
)
from general.forms import ParametresEntrepriseForm
from general.mixins import AgenceScopedMixin
from general.models import Agence, ParametresEntreprise
from sales.models import Commande


class AgenceDashboardView(LoginRequiredMixin, AgenceScopedMixin, TemplateView):
    """Tableau de bord d'une agence précise : /agences/<slug>/dashboard/.

    Accessible au Responsable/Caissier de cette agence, et à tout Admin qui
    consulte cette agence en particulier (EF-9.2, EF-12.4). ``self.agence``
    est posé par AgenceScopedMixin.dispatch() avant même que get() ne
    s'exécute (et c'est aussi lui qui bloque un utilisateur non autorisé à
    voir cette agence — rien à revérifier ici).
    """

    template_name = "dashboard/pages/general/dashboard_home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        periode = resoudre_periode(self.request)
        commandes_agence = Commande.objects.filter(agence=self.agence)

        est_caissier = getattr(self.request.user, "is_caissier", False)
        if est_caissier:
            # EF-9.4 : un Caissier ne voit QUE ses propres ventes, jamais
            # celles de ses collègues de la même agence.
            commandes_scope = commandes_agence.filter(caissier=self.request.user)
        else:
            commandes_scope = commandes_agence

        commandes_periode = appliquer_periode(commandes_scope, periode)

        context.update(
            {
                "periode": periode,
                "kpis": calculer_kpis_ventes(commandes_periode),
                "serie_ca": serie_ca_dans_le_temps(commandes_periode, periode),
                "ventes_paiement": ventes_par_mode_paiement(commandes_periode),
                "ventes_recentes": commandes_periode.filter(statut__in=STATUTS_TRANSACTION)
                .select_related("caissier", "client")
                .order_by("-date")[:8],
            }
        )

        if est_caissier:
            context["dashboard_mode"] = "caissier"
        else:
            stock_bas_qs = produits_stock_bas(agence=self.agence)
            context.update(
                {
                    "dashboard_mode": "agence",
                    "top_produits": top_produits(commandes_periode),
                    "ventes_categorie": ventes_par_categorie(commandes_periode),
                    "performance_caissiers": performance_caissiers(commandes_periode),
                    "produits_stock_bas_total": stock_bas_qs.count(),
                    "produits_stock_bas": stock_bas_qs[:8],
                    "valeur_stock": valeur_stock(agence=self.agence),
                }
            )
        return context


class AdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Tableau de bord global, toutes agences confondues (EF-9.2, EF-12.4)."""

    template_name = "dashboard/pages/general/dashboard_home.html"

    def test_func(self) -> bool:
        return getattr(self.request.user, "is_admin", False)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["agence"] = None

        periode = resoudre_periode(self.request)
        commandes_periode = appliquer_periode(Commande.objects.all(), periode)

        agences = Agence.objects.all().order_by("nom")
        ca_map = ca_par_agence_map(commandes_periode)
        stock_bas_map = stock_bas_par_agence_map()
        agences_apercu = [
            {
                "agence": agence,
                "ca": ca_map.get(agence.id, Decimal("0")),
                "stock_bas": stock_bas_map.get(agence.id, 0),
            }
            for agence in agences
        ]
        stock_bas_qs = produits_stock_bas(agences_qs=agences)

        context.update(
            {
                "dashboard_mode": "global",
                "periode": periode,
                "kpis": calculer_kpis_ventes(commandes_periode),
                "serie_ca": serie_ca_dans_le_temps(commandes_periode, periode),
                "ventes_paiement": ventes_par_mode_paiement(commandes_periode),
                "top_produits": top_produits(commandes_periode),
                "ventes_categorie": ventes_par_categorie(commandes_periode),
                "ca_par_agence": ca_par_agence(commandes_periode),
                "agences_apercu": agences_apercu,
                "produits_stock_bas_total": stock_bas_qs.count(),
                "produits_stock_bas": stock_bas_qs[:8],
                "valeur_stock": valeur_stock(agences_qs=agences),
                "ventes_recentes": commandes_periode.filter(statut__in=STATUTS_TRANSACTION)
                .select_related("agence", "caissier", "client")
                .order_by("-date")[:8],
            }
        )
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