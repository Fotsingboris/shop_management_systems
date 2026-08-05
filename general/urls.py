"""Routes de l'app general.

Si un general/urls.py existe déjà chez vous avec d'autres routes,
fusionnez ces `path()` dedans plutôt que d'écraser le fichier.
"""
from __future__ import annotations

from django.urls import path

from general.views.admin_dashboard import AdminDashboardView, AgenceDashboardView, ParametresEntrepriseUpdateView
from general.views import agency_views as views
from general.views.report_views import (
    InventaireExportExcelView,
    InventaireExportPdfView,
    InventaireReportView,
    VenteExportExcelView,
    VenteExportPdfView,
    VenteReportView,
)

app_name = "general"

urlpatterns = [
    path("dashboard/", AdminDashboardView.as_view(), name="dashboard"),
    path(
        "agences/<slug:agence_slug>/dashboard/",
        AgenceDashboardView.as_view(),
        name="agence_dashboard",
    ),
    path("parametres/", ParametresEntrepriseUpdateView.as_view(), name="parametres"),

    # anagecy
    path("agences/", views.AgenceListView.as_view(), name="agence_list"),
    path("agences/nouvelle/", views.AgenceCreateView.as_view(), name="agence_create"),
    path("agences/<slug:slug>/modifier/", views.AgenceUpdateView.as_view(), name="agence_update"),

    # Rapports (EF-9.3, EF-11, EF-12) : inventaire + ventes, chacun avec ses
    # deux exports (Excel / PDF), qui ré-appliquent les mêmes filtres.
    path("rapports/inventaire/", InventaireReportView.as_view(), name="rapport_inventaire"),
    path(
        "rapports/inventaire/export/excel/",
        InventaireExportExcelView.as_view(),
        name="rapport_inventaire_export_excel",
    ),
    path(
        "rapports/inventaire/export/pdf/",
        InventaireExportPdfView.as_view(),
        name="rapport_inventaire_export_pdf",
    ),
    path("rapports/ventes/", VenteReportView.as_view(), name="rapport_ventes"),
    path(
        "rapports/ventes/export/excel/",
        VenteExportExcelView.as_view(),
        name="rapport_ventes_export_excel",
    ),
    path(
        "rapports/ventes/export/pdf/",
        VenteExportPdfView.as_view(),
        name="rapport_ventes_export_pdf",
    ),
]