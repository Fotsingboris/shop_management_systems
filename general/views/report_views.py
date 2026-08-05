"""Vues des rapports d'inventaire et de ventes (EF-9.3, EF-11, EF-12).

Réservées à l'encadrement (Admin : toutes les agences ; Responsable
d'agence : la sienne uniquement — EF-9.3 mentionne explicitement les
"rapports" dans son périmètre, au même titre que les caissiers).

Chaque rapport a 3 vues : la page (ListView, paginée) et deux exports
(Excel / PDF) qui ré-appliquent exactement les mêmes filtres et le même
périmètre, mais SANS pagination — l'export doit contenir tout ce que les
filtres sélectionnent, pas seulement la page actuellement affichée.
"""
from __future__ import annotations

from typing import Any, Dict

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.utils import timezone
from django.views import View
from django.views.generic import ListView

from general.enums import CommandeStatut
from general.models import ParametresEntreprise
from general.report_exports import exporter_excel, exporter_pdf
from general.reports_services import (
    calculer_kpis_inventaire,
    calculer_kpis_ventes,
    get_agences_autorisees,
    get_caissiers_pour_filtre,
    get_categories_pour_filtre,
    get_inventaire_queryset,
    get_lignes_ventes_queryset,
    get_produits_pour_filtre,
    resoudre_filtres_inventaire,
    resoudre_filtres_ventes,
)
from products.models import ProduitAgence
from sales.models import LigneCommande


class RapportsAccessMixin(UserPassesTestMixin):
    """Réservé à l'encadrement : Admin ou Responsable d'agence (EF-9.3)."""

    def test_func(self) -> bool:
        return getattr(self.request.user, "is_admin", False) or getattr(
            self.request.user, "is_responsable_agence", False
        )


# --------------------------------------------------------------------------
# Inventaire
# --------------------------------------------------------------------------


class InventaireReportView(LoginRequiredMixin, RapportsAccessMixin, ListView):
    """Rapport d'inventaire : état du stock, filtrable par agence/catégorie/produit."""

    model = ProduitAgence
    template_name = "dashboard/pages/general/reports/inventaire.html"
    context_object_name = "lignes_stock"
    paginate_by = 25

    def get_queryset(self):
        self.filtres = resoudre_filtres_inventaire(self.request)
        return get_inventaire_queryset(self.request.user, self.filtres)

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        request = self.request

        # `self.object_list` est le queryset COMPLET (avant pagination) :
        # les KPIs doivent porter sur l'ensemble filtré, pas la page affichée.
        context["kpis"] = calculer_kpis_inventaire(self.object_list)
        context["filtres"] = self.filtres
        context["est_admin"] = getattr(request.user, "is_admin", False)
        context["agences"] = get_agences_autorisees(request.user)
        context["categories"] = get_categories_pour_filtre()
        context["querystring_export"] = request.GET.urlencode()
        context["vue_active"] = "inventaire"
        context["parametres"] = ParametresEntreprise.load()
        return context


def _lignes_excel_inventaire(qs):
    for ligne in qs:
        yield [
            ligne.agence.nom,
            ligne.produit.nom,
            ligne.produit.sku,
            ligne.produit.categorie.nom,
            float(ligne.prix_vente),
            ligne.stock_quantite,
            ligne.seuil_alerte,
            "Stock bas" if ligne.stock_bas else "OK",
            "Actif" if ligne.actif else "Inactif",
        ]


class InventaireExportExcelView(LoginRequiredMixin, RapportsAccessMixin, View):
    def get(self, request, *args, **kwargs):
        filtres = resoudre_filtres_inventaire(request)
        qs = get_inventaire_queryset(request.user, filtres)
        entetes = [
            "Agence", "Produit", "SKU", "Catégorie", "Prix de vente",
            "Stock", "Seuil alerte", "Statut stock", "Statut fiche",
        ]
        nom_fichier = f"inventaire_{timezone.localdate():%Y%m%d}.xlsx"
        return exporter_excel(
            nom_fichier=nom_fichier,
            entetes=entetes,
            lignes=_lignes_excel_inventaire(qs),
            titre="Rapport d'inventaire",
        )


class InventaireExportPdfView(LoginRequiredMixin, RapportsAccessMixin, View):
    def get(self, request, *args, **kwargs):
        filtres = resoudre_filtres_inventaire(request)
        qs = get_inventaire_queryset(request.user, filtres)
        contexte = {
            "parametres": ParametresEntreprise.load(),
            "lignes": qs,
            "kpis": calculer_kpis_inventaire(qs),
            "genere_le": timezone.now(),
            "genere_par": request.user,
        }
        nom_fichier = f"inventaire_{timezone.localdate():%Y%m%d}.pdf"
        return exporter_pdf(
            nom_fichier=nom_fichier,
            nom_gabarit="dashboard/pages/general/reports/pdf/inventaire_pdf.html",
            contexte=contexte,
        )


# --------------------------------------------------------------------------
# Ventes
# --------------------------------------------------------------------------


class VenteReportView(LoginRequiredMixin, RapportsAccessMixin, ListView):
    """Rapport de ventes : détail ligne par ligne, filtrable par agence/vendeur/catégorie/produit/période."""

    model = LigneCommande
    template_name = "dashboard/pages/general/reports/ventes.html"
    context_object_name = "lignes_ventes"
    paginate_by = 25

    def get_queryset(self):
        self.filtres = resoudre_filtres_ventes(self.request)
        return get_lignes_ventes_queryset(self.request.user, self.filtres)

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        request = self.request

        context["kpis"] = calculer_kpis_ventes(self.object_list)
        context["filtres"] = self.filtres
        context["est_admin"] = getattr(request.user, "is_admin", False)
        context["agences"] = get_agences_autorisees(request.user)
        context["categories"] = get_categories_pour_filtre()
        context["produits"] = get_produits_pour_filtre()
        context["caissiers"] = get_caissiers_pour_filtre(request.user, self.filtres.agence_id)
        context["statuts"] = CommandeStatut.choices
        context["querystring_export"] = request.GET.urlencode()
        context["vue_active"] = "ventes"
        context["parametres"] = ParametresEntreprise.load()
        return context


def _lignes_excel_ventes(qs):
    for ligne in qs:
        commande = ligne.commande
        yield [
            timezone.localtime(commande.date).strftime("%d/%m/%Y %H:%M"),
            str(commande.id)[:8].upper(),
            commande.agence.nom,
            commande.caissier.get_full_name() or commande.caissier.username,
            commande.client.nom if commande.client_id else "Client de passage",
            ligne.produit.nom,
            ligne.produit.categorie.nom,
            ligne.quantite,
            float(ligne.prix_unitaire),
            float(ligne.sous_total),
            commande.get_statut_display(),
        ]


class VenteExportExcelView(LoginRequiredMixin, RapportsAccessMixin, View):
    def get(self, request, *args, **kwargs):
        filtres = resoudre_filtres_ventes(request)
        qs = get_lignes_ventes_queryset(request.user, filtres)
        entetes = [
            "Date", "N° vente", "Agence", "Vendeur", "Client",
            "Produit", "Catégorie", "Quantité", "Prix unitaire", "Sous-total", "Statut",
        ]
        nom_fichier = f"ventes_{timezone.localdate():%Y%m%d}.xlsx"
        return exporter_excel(
            nom_fichier=nom_fichier,
            entetes=entetes,
            lignes=_lignes_excel_ventes(qs),
            titre="Rapport de ventes",
        )


class VenteExportPdfView(LoginRequiredMixin, RapportsAccessMixin, View):
    def get(self, request, *args, **kwargs):
        filtres = resoudre_filtres_ventes(request)
        qs = get_lignes_ventes_queryset(request.user, filtres)
        contexte = {
            "parametres": ParametresEntreprise.load(),
            "lignes": qs,
            "filtres": filtres,
            "kpis": calculer_kpis_ventes(qs),
            "genere_le": timezone.now(),
            "genere_par": request.user,
        }
        nom_fichier = f"ventes_{timezone.localdate():%Y%m%d}.pdf"
        return exporter_pdf(
            nom_fichier=nom_fichier,
            nom_gabarit="dashboard/pages/general/reports/pdf/ventes_pdf.html",
            contexte=contexte,
        )