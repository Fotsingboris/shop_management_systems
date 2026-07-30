"""Routes de l'app users.

Si un users/urls.py existe déjà chez vous, fusionnez ces `path()` dedans
plutôt que d'écraser le fichier.
"""
from __future__ import annotations

from django.contrib.auth.views import LogoutView
from django.urls import path

from users.views.auth_views import UtilisateurLoginView, UtilisateurCreateView

app_name = "users"

urlpatterns = [
    path("connexion/", UtilisateurLoginView.as_view(), name="login"),
    path("deconnexion/", LogoutView.as_view(next_page="users:login"), name="logout"),
    path("creer-compte/", UtilisateurCreateView.as_view(), name="creer_compte"),
]