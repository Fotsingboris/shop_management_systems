"""Template tags pour la navigation du tableau de bord (lien + état actif)."""
from __future__ import annotations

from typing import Any, Dict

from django import template

from general.utils import resolve_dashboard_url

register = template.Library()

ACTIVE_CLASSES = "nav-link-active bg-primary-800 text-white"
INACTIVE_CLASSES = "text-primary-100 hover:bg-primary-800 hover:text-white"


@register.simple_tag(takes_context=True)
def dashboard_url(context: Dict[str, Any]) -> str:
    """URL du tableau de bord de l'utilisateur courant (rôle + agence).

    Réutilise la même logique que la redirection post-connexion
    (general.utils.resolve_dashboard_url) : évite de dupliquer le "Admin ->
    dashboard global, sinon -> dashboard de son agence" dans les templates.
    """
    request = context["request"]
    if not request.user.is_authenticated:
        return ""
    return resolve_dashboard_url(request.user)


@register.simple_tag(takes_context=True)
def nav_active(context: Dict[str, Any], *view_names: str) -> str:
    """Classes CSS à appliquer si la page courante correspond à l'un de ``view_names``.

    ``view_names`` sont des noms de vue complets (ex: "general:dashboard").
    Une entrée de nav peut être active pour plusieurs vues à la fois (ex: le
    tableau de bord est à la fois "general:dashboard" pour un Admin et
    "general:agence_dashboard" pour un Responsable/Caissier).

    Usage :
        class="nav-link ... {% nav_active 'general:dashboard' 'general:agence_dashboard' %}"
    """
    request = context["request"]
    match = getattr(request, "resolver_match", None)
    current_view_name = getattr(match, "view_name", None) if match else None
    return ACTIVE_CLASSES if current_view_name in view_names else INACTIVE_CLASSES