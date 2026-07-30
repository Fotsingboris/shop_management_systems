"""Vues d'authentification et de création de compte (EF-9)."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView

from general.utils import resolve_dashboard_url
from users.forms import UtilisateurCreationForm
from users.models import Utilisateur


class UtilisateurLoginView(LoginView):
    """Connexion : redirige ensuite vers le tableau de bord adapté au rôle.

    On surcharge ``get_default_redirect_url`` (pas ``get_success_url``) pour
    ne pas casser la gestion habituelle du paramètre ``?next=`` par Django :
    si quelqu'un est renvoyé vers la connexion depuis une page précise, il y
    retourne après authentification ; sinon, redirection basée sur le rôle.
    """

    template_name = "auth/login.html"
    redirect_authenticated_user = True

    def get_default_redirect_url(self) -> str:
        return resolve_dashboard_url(self.request.user)


class UtilisateurCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Création d'un compte employé (EF-9.2, EF-9.3).

    Pas d'inscription publique : réservé à l'Admin (tous rôles, toutes
    agences) et au Responsable d'agence (Caissiers de sa propre agence
    uniquement — appliqué à la fois dans le formulaire et dans test_func).
    """

    model = Utilisateur
    form_class = UtilisateurCreationForm
    template_name = "users/register.html"
    success_url = reverse_lazy("users:creer_compte")

    def test_func(self) -> bool:
        user = self.request.user
        return bool(getattr(user, "is_admin", False) or getattr(user, "is_responsable_agence", False))

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["created_by"] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            _("Compte créé pour %(username)s.") % {"username": self.object.username},
        )
        return response