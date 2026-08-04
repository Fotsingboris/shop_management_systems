"""Fonctions transverses (mise en cache, périmètre agences) du catalogue produit.

Les fonctions de périmètre par agence (``get_agences_autorisees``,
``get_agences_visibles``) vivaient à l'origine dans ``stock_views.py``.
Elles sont ici, dans un module neutre, pour que ``forms.py`` (TransfertStockForm)
et ``stock_views.py`` puissent toutes les deux les importer sans import
circulaire (``stock_views`` importe déjà des classes de ``forms``).
"""
from __future__ import annotations

from typing import List

from django.core.cache import cache
from django.db.models import QuerySet

from general.models import Agence
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


def get_agences_autorisees(user) -> QuerySet[Agence]:
    """Agences actives que ``user`` a le droit de configurer (stock/prix, transferts).

    Admin : toutes les agences actives. Responsable d'agence : uniquement
    la sienne (et seulement si elle est active). Tout autre cas (Caissier,
    Responsable sans agence) : aucune.
    """
    if getattr(user, "is_admin", False):
        return Agence.objects.filter(actif=True).order_by("nom")
    if getattr(user, "is_responsable_agence", False) and user.agence_id:
        return Agence.objects.filter(pk=user.agence_id, actif=True)
    return Agence.objects.none()


def get_agences_visibles(user) -> QuerySet[Agence]:
    """Agences dont ``user`` peut CONSULTER le stock/prix, pour les listes (EF-1.3, EF-13.3).

    Différent de ``get_agences_autorisees()`` (qui ne sert qu'à choisir où
    AJOUTER/transférer du stock, donc uniquement des agences actives) :
    une agence désactivée "reste visible dans l'historique et les
    rapports" (EF-1.3), donc les listes ne filtrent pas sur ``actif``.
    """
    if getattr(user, "is_admin", False):
        return Agence.objects.all()
    if getattr(user, "is_responsable_agence", False) and user.agence_id:
        return Agence.objects.filter(pk=user.agence_id)
    return Agence.objects.none()