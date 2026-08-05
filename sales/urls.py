"""Routes de l'app sales (point de vente).

Si un sales/urls.py existe déjà chez vous, fusionnez ces `path()` dedans
plutôt que d'écraser le fichier, et n'oubliez pas de brancher
``path("ventes/", include("sales.urls"))`` (ou équivalent) dans les urls
du projet si ce n'est pas déjà fait.
"""
from __future__ import annotations

from django.urls import path

from sales.views import pos_views

app_name = "sales"

urlpatterns = [
    # Point de vente (Create)
    path("ventes/nouvelle/", pos_views.CommandeCreateView.as_view(), name="commande_create"),
    path(
        "ventes/recherche-produits/",
        pos_views.POSProduitRechercheApiView.as_view(),
        name="pos_produit_recherche",
    ),
    path(
        "ventes/recherche-clients/",
        pos_views.ClientRechercheApiView.as_view(),
        name="client_recherche",
    ),
    # Historique des ventes (Read)
    path("ventes/", pos_views.CommandeListView.as_view(), name="commande_list"),
    path("ventes/<uuid:pk>/", pos_views.CommandeDetailView.as_view(), name="commande_detail"),
    # Annuler / rembourser (Update)
    path(
        "ventes/<uuid:pk>/statut/",
        pos_views.CommandeStatutUpdateView.as_view(),
        name="commande_statut_update",
    ),
    # Reçu PDF (généré à la volée si besoin)
    path("ventes/<uuid:pk>/recu/", pos_views.RecuDownloadView.as_view(), name="recu_download"),
]