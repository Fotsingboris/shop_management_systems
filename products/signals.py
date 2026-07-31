"""Invalidation de cache pour le catalogue produit."""
from __future__ import annotations

from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from products.models import Categorie
from products.services import CATEGORIES_ACTIVES_CACHE_KEY


@receiver(post_save, sender=Categorie)
@receiver(post_delete, sender=Categorie)
def invalidate_categories_actives_cache(sender, **kwargs) -> None:
    """Vide le cache de la liste des catégories actives (products.services).

    Se déclenche aussi bien pour une création/modification manuelle
    (formulaire admin) que pour celles faites par l'import Excel de
    produits (products.tasks.importer_produits), puisque les deux passent
    par Categorie.save().
    """
    cache.delete(CATEGORIES_ACTIVES_CACHE_KEY)