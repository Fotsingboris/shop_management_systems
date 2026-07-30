"""Routes de l'app general.

Si un general/urls.py existe déjà chez vous avec d'autres routes,
fusionnez ces deux `path()` dedans plutôt que d'écraser le fichier.
"""
from __future__ import annotations

from django.urls import path

from general.views.admin_dashboard import AdminDashboardView, AgenceDashboardView, ParametresEntrepriseUpdateView

app_name = "general"

urlpatterns = [
    path("dashboard/", AdminDashboardView.as_view(), name="dashboard"),
    path(
        "agences/<slug:agence_slug>/dashboard/",
        AgenceDashboardView.as_view(),
        name="agence_dashboard",
    ),
    path("parametres/", ParametresEntrepriseUpdateView.as_view(), name="parametres"),
]