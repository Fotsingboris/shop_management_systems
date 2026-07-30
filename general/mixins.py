"""Mixins de vues partagés par toute l'application."""
from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect

from general.models import Agence
from general.utils import resolve_dashboard_url


class AgenceScopedMixin:
    """Résout l'agence depuis le slug d'URL et vérifie l'accès (EF-9.5).

    - Admin : accès à n'importe quelle agence (EF-9.2), y compris pour
      consulter une agence désactivée dans l'historique/les rapports (EF-1.3).
    - ResponsableAgence / Caissier : uniquement leur propre agence. En cas
      de tentative sur le slug d'une autre agence, redirection silencieuse
      vers LEUR propre tableau de bord plutôt qu'un 403/404 qui confirmerait
      l'existence du slug visé.

    Important : ce mixin protège l'accès à la VUE. Chaque vue concrète doit
    EN PLUS filtrer explicitement ses querysets par ``self.agence`` — ce
    mixin ne fait aucune hypothèse sur les données affichées (EF-9.5 exige
    les deux niveaux de contrôle, pas seulement l'un ou l'autre).
    """

    agence_slug_url_kwarg: str = "agence_slug"
    agence: Agence

    def dispatch(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        self.agence = get_object_or_404(Agence, slug=kwargs[self.agence_slug_url_kwarg])
        user = request.user
        is_admin = getattr(user, "is_admin", False)
        user_agence_id = getattr(user, "agence_id", None)
        if not is_admin and user_agence_id != self.agence.id:
            return redirect(resolve_dashboard_url(user))
        return super().dispatch(request, *args, **kwargs)  # type: ignore[misc]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)  # type: ignore[misc]
        context["agence"] = self.agence
        return context