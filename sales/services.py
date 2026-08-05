"""Fonctions de portée pour les ventes / point de vente (EF-7, EF-9).

Fichier séparé (comme products/services.py) plutôt que de dupliquer cette
logique dans chaque vue : sales/pos_views.py l'utilise pour le
create/list/detail/statut, et pourra être réutilisé plus tard par un
éventuel module de rapports (EF-11).
"""
from __future__ import annotations

from django.db.models import QuerySet

from sales.models import Commande


def get_commandes_visibles(user) -> QuerySet[Commande]:
    """Ventes visibles par ``user`` (EF-7.5, EF-9.2 à EF-9.4).

    - Admin : toutes les ventes, toutes agences confondues.
    - Responsable d'agence : uniquement les ventes de SA propre agence,
      réalisées par n'importe quel caissier de cette agence — y compris si
      l'agence a depuis été désactivée (cohérent avec EF-1.3 : une agence
      désactivée reste visible dans l'historique/les rapports).
    - Caissier : uniquement les ventes QU'IL a lui-même réalisées
      ("son historique", EF-9.4) — pas celles de ses collègues, même dans
      la même agence.
    - Tout autre cas (rôle inconnu/absent) : aucune vente.
    """
    if getattr(user, "is_admin", False):
        return Commande.objects.all()
    if getattr(user, "is_responsable_agence", False) and user.agence_id:
        return Commande.objects.filter(agence_id=user.agence_id)
    if getattr(user, "is_caissier", False):
        return Commande.objects.filter(caissier=user)
    return Commande.objects.none()