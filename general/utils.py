"""Fonctions utilitaires génériques, réutilisables par tous les modèles.

Ne dépend d'aucun modèle concret : peut être importé depuis n'importe
quelle application (general, users, products, sales) sans risque de
cycle d'import.
"""
from __future__ import annotations

from typing import Any, Optional, Type

from django.db import models
from django.utils.text import slugify


def generate_unique_slug(
    instance: models.Model,
    source_field_name: str,
    slug_field_name: str = "slug",
    max_length: Optional[int] = None,
) -> str:
    """Génère un slug unique pour ``instance`` à partir d'un autre champ.

    Utilisable par n'importe quel modèle possédant un champ slug (Agence,
    Categorie, Produit...) : évite de dupliquer cette logique dans chaque
    ``save()``. En cas de collision, ajoute un suffixe numérique
    (``-1``, ``-2``, ...) et exclut l'instance courante lors d'une mise
    à jour, pour ne pas se comparer à elle-même.

    Exemple :
        if not self.slug:
            self.slug = generate_unique_slug(self, "nom")
    """
    model: Type[models.Model] = instance.__class__
    slug_field = model._meta.get_field(slug_field_name)
    max_length = max_length or slug_field.max_length

    source_value = getattr(instance, source_field_name)
    base_slug = slugify(source_value)[:max_length] or "item"

    queryset = model._default_manager.all()
    if instance.pk is not None:
        queryset = queryset.exclude(pk=instance.pk)

    slug = base_slug
    counter = 1
    while queryset.filter(**{slug_field_name: slug}).exists():
        suffix = f"-{counter}"
        slug = f"{base_slug[: max_length - len(suffix)]}{suffix}"
        counter += 1

    return slug


def resolve_dashboard_url(user: Any) -> str:
    """URL du tableau de bord adapté à cet utilisateur, après connexion.

    Écrit en "duck typing" (``is_admin`` / ``agence``) plutôt que d'importer
    ``users.models.Utilisateur`` : general ne doit dépendre d'aucune autre
    application (voir le découplage general -> users -> products -> sales).

    - Admin (ou tout utilisateur sans agence assignée, cas de repli) :
      tableau de bord global (EF-9.2, EF-12.4).
    - Autres rôles : tableau de bord de leur propre agence, adressé par
      son slug plutôt que son UUID.
    """
    from django.urls import reverse  # import local : évite un cycle au chargement des apps

    if not getattr(user, "is_admin", False):
        agence = getattr(user, "agence", None)
        if agence is not None:
            return reverse("general:agence_dashboard", kwargs={"agence_slug": agence.slug})
    return reverse("general:dashboard")