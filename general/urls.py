"""Routes de l'app general.

Si un general/urls.py existe déjà chez vous avec d'autres routes,
fusionnez ces deux `path()` dedans plutôt que d'écraser le fichier.
"""
from __future__ import annotations

from django.urls import path

from general.views.admin_dashboard import AdminDashboardView, AgenceDashboardView, ParametresEntrepriseUpdateView
from general.views import agency_views as views

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
    path("agences/<slug:slug>/modifier/", views.AgenceUpdateView.as_view(), name="agence_update")
]