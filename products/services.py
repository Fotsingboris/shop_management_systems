"""Fonctions transverses (mise en cache) du catalogue produit."""
from __future__ import annotations

from typing import List

from django.core.cache import cache

from products.models import Categorie

CATEGORIES_ACTIVES_CACHE_KEY = "products:categories_actives"


def get_categories_actives() -> List[Categorie]:
    """Catégories actives, pour peupler un filtre déroulant (EF-13.1).

    Mise en cache sans expiration, à la manière de
    ``ParametresEntreprise.load()`` : la liste est invalidée par
    ``products.signals`` dès qu'une Categorie est créée, modifiée ou
    supprimée (y compris via l'import Excel, qui appelle le même
    ``Categorie.save()``).

    Ne PAS utiliser cette fonction pour peupler un ModelChoiceField de
    formulaire : elle renvoie une liste, pas un queryset, et
    ModelChoiceField a besoin d'un vrai queryset pour valider les valeurs
    soumises (voir ProduitForm, qui interroge la base directement).
    """
    categories = cache.get(CATEGORIES_ACTIVES_CACHE_KEY)
    if categories is None:
        categories = list(Categorie.objects.filter(actif=True).order_by("nom"))
        cache.set(CATEGORIES_ACTIVES_CACHE_KEY, categories, None)
    return categories