"""Fonctions de portée pour la gestion des utilisateurs (EF-9)."""
from __future__ import annotations

from django.db.models import QuerySet

from general.enums import Role
from users.models import Utilisateur


def get_utilisateurs_visibles(user) -> QuerySet[Utilisateur]:
    """Comptes que ``user`` peut voir ET gérer (créer/modifier/activer-désactiver).

    - Admin : tous les comptes, tous rôles confondus.
    - Responsable d'agence : uniquement les Caissiers de SA propre agence
      (EF-9.3 : "limité ... pour prix/stock, caissiers et rapports") — pas
      les autres Responsables, pas les Admins, pas les caissiers d'une
      autre agence.
    - Tout autre cas (Caissier, ou rôle absent) : aucun compte — cette
      fonctionnalité ne leur est pas destinée.
    """
    if getattr(user, "is_admin", False):
        return Utilisateur.objects.all()
    if getattr(user, "is_responsable_agence", False) and user.agence_id:
        return Utilisateur.objects.filter(agence_id=user.agence_id, role=Role.CAISSIER)
    return Utilisateur.objects.none()