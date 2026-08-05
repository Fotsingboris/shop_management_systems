"""Filtres et requêtes des rapports d'inventaire et de ventes (EF-9.3, EF-11, EF-12).

Vit dans `general` (comme `dashboard_services.py`, qui agrège déjà des
données `sales`/`products` pour les tableaux de bord) plutôt que dans une
app dédiée : ces rapports croisent délibérément agences, catégories,
produits et utilisateurs, quatre domaines différents, et n'appartiennent
naturellement à aucune app métier en particulier.

Portée (même règle que pour la gestion des utilisateurs, EF-9.3 : "...
limité ... pour prix/stock, caissiers et rapports") :
- Admin : toutes les agences, tous filtres ouverts.
- Responsable d'agence : uniquement SA propre agence ; le filtre "agence"
  est alors verrouillé côté vue (jamais fait confiance au client).
- Caissier : aucun accès (cf. RapportsAccessMixin dans les vues).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional

from django.db.models import DecimalField, F, Q, QuerySet, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from general.enums import CommandeStatut
from general.models import Agence
from products.models import Categorie, Produit, ProduitAgence
from sales.models import LigneCommande

STATUTS_COMPTABILISABLES = [CommandeStatut.TERMINEE, CommandeStatut.REMBOURSEE]


def agence_fixe_pour(user) -> Optional[Agence]:
    """Agence à laquelle `user` est restreint, ou None si non restreint (Admin)."""
    if getattr(user, "is_admin", False):
        return None
    return getattr(user, "agence", None)


def get_agences_autorisees(user) -> QuerySet[Agence]:
    """Agences que `user` peut sélectionner dans le filtre "Agence" (EF-9.2, EF-9.3)."""
    if getattr(user, "is_admin", False):
        return Agence.objects.all().order_by("nom")
    agence = agence_fixe_pour(user)
    if agence is not None:
        return Agence.objects.filter(pk=agence.pk)
    return Agence.objects.none()


def get_categories_pour_filtre() -> QuerySet[Categorie]:
    return Categorie.objects.filter(actif=True).order_by("nom")


def get_produits_pour_filtre() -> QuerySet[Produit]:
    return Produit.objects.filter(actif=True).order_by("nom")


def get_caissiers_pour_filtre(user, agence_id_filtre: str = "") -> QuerySet[Any]:
    """Utilisateurs proposés dans le filtre "Vendeur" du rapport de ventes.

    N'importe quel rôle peut avoir réalisé une vente depuis l'élargissement
    du POS (Admin/Responsable/Caissier) : on ne filtre donc pas sur
    `role=CAISSIER`, seulement sur l'agence visible par `user`.
    """
    from users.models import Utilisateur

    agence_fixe = agence_fixe_pour(user)
    qs = Utilisateur.objects.all()
    if agence_fixe is not None:
        qs = qs.filter(agence=agence_fixe)
    elif agence_id_filtre:
        qs = qs.filter(agence_id=agence_id_filtre)
    elif not getattr(user, "is_admin", False):
        return Utilisateur.objects.none()
    return qs.order_by("first_name", "last_name", "username")


def _parse_date(valeur: str) -> Optional[date]:
    try:
        return datetime.strptime(valeur, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


# --------------------------------------------------------------------------
# Inventaire
# --------------------------------------------------------------------------


@dataclass
class FiltresInventaire:
    agence_id: str = ""
    categorie_id: str = ""
    q: str = ""
    stock_bas_seulement: bool = False
    statut: str = ""  # "actif" | "inactif" | ""


def resoudre_filtres_inventaire(request) -> FiltresInventaire:
    get = request.GET
    return FiltresInventaire(
        agence_id=get.get("agence", "").strip(),
        categorie_id=get.get("categorie", "").strip(),
        q=get.get("q", "").strip(),
        stock_bas_seulement=get.get("stock_bas") == "1",
        statut=get.get("statut", "").strip(),
    )


def get_inventaire_queryset(user, filtres: FiltresInventaire) -> QuerySet[ProduitAgence]:
    """Lignes de stock visibles par `user`, avec les filtres appliqués.

    Le filtre "agence" envoyé par un Responsable est ignoré : sa portée est
    revalidée ici à partir de `user.agence`, jamais du paramètre GET brut.
    """
    qs = ProduitAgence.objects.select_related("produit", "produit__categorie", "agence")

    agence_fixe = agence_fixe_pour(user)
    if agence_fixe is not None:
        qs = qs.filter(agence=agence_fixe)
    elif filtres.agence_id:
        qs = qs.filter(agence_id=filtres.agence_id)

    if filtres.categorie_id:
        qs = qs.filter(produit__categorie_id=filtres.categorie_id)

    if filtres.q:
        qs = qs.filter(Q(produit__nom__icontains=filtres.q) | Q(produit__sku__icontains=filtres.q))

    if filtres.statut == "actif":
        qs = qs.filter(actif=True)
    elif filtres.statut == "inactif":
        qs = qs.filter(actif=False)

    if filtres.stock_bas_seulement:
        qs = qs.filter(stock_quantite__lte=F("seuil_alerte"))

    return qs.order_by("agence__nom", "produit__nom")


def calculer_kpis_inventaire(qs: QuerySet[ProduitAgence]) -> dict:
    """KPIs affichés au-dessus du tableau.

    `qs` doit être NON tronqué (pas de pagination) : on compte/agrège
    d'abord, la vue ne découpe en pages qu'ensuite (jamais l'inverse, sous
    peine de ne compter que la page affichée).
    """
    agg = qs.aggregate(
        stock_total=Coalesce(Sum("stock_quantite"), 0),
        valeur_stock=Coalesce(
            Sum(F("stock_quantite") * F("produit__prix_achat"), output_field=DecimalField(max_digits=14, decimal_places=2)),
            Value(Decimal("0"), output_field=DecimalField(max_digits=14, decimal_places=2)),
        ),
    )
    agg["nombre_references"] = qs.count()
    agg["nombre_alertes"] = qs.filter(stock_quantite__lte=F("seuil_alerte")).count()
    return agg


# --------------------------------------------------------------------------
# Ventes
# --------------------------------------------------------------------------


@dataclass
class FiltresVentes:
    agence_id: str = ""
    caissier_id: str = ""
    categorie_id: str = ""
    produit_id: str = ""
    statut: str = ""
    date_debut: Optional[date] = None
    date_fin: Optional[date] = None


def resoudre_filtres_ventes(request) -> FiltresVentes:
    get = request.GET
    date_debut = _parse_date(get.get("date_debut", ""))
    date_fin = _parse_date(get.get("date_fin", ""))
    a_une_date_explicite = bool(get.get("date_debut") or get.get("date_fin"))
    if not a_une_date_explicite:
        # Par défaut : les 30 derniers jours, comme les tableaux de bord.
        date_fin = timezone.localdate()
        date_debut = date_fin - timedelta(days=29)

    return FiltresVentes(
        agence_id=get.get("agence", "").strip(),
        caissier_id=get.get("caissier", "").strip(),
        categorie_id=get.get("categorie", "").strip(),
        produit_id=get.get("produit", "").strip(),
        statut=get.get("statut", "").strip(),
        date_debut=date_debut,
        date_fin=date_fin,
    )


def get_lignes_ventes_queryset(user, filtres: FiltresVentes) -> QuerySet[LigneCommande]:
    """Lignes de commande visibles par `user`, avec les filtres appliqués.

    Ligne par ligne (et non commande par commande) pour permettre les
    filtres "catégorie" et "produit" demandés, qui n'ont de sens qu'au
    niveau de la ligne.
    """
    qs = LigneCommande.objects.select_related(
        "commande",
        "commande__agence",
        "commande__caissier",
        "commande__client",
        "produit",
        "produit__categorie",
    )

    agence_fixe = agence_fixe_pour(user)
    if agence_fixe is not None:
        qs = qs.filter(commande__agence=agence_fixe)
    elif filtres.agence_id:
        qs = qs.filter(commande__agence_id=filtres.agence_id)

    if filtres.caissier_id:
        qs = qs.filter(commande__caissier_id=filtres.caissier_id)

    if filtres.categorie_id:
        qs = qs.filter(produit__categorie_id=filtres.categorie_id)

    if filtres.produit_id:
        qs = qs.filter(produit_id=filtres.produit_id)

    if filtres.statut:
        qs = qs.filter(commande__statut=filtres.statut)
    else:
        qs = qs.filter(commande__statut__in=STATUTS_COMPTABILISABLES)

    if filtres.date_debut:
        qs = qs.filter(commande__date__date__gte=filtres.date_debut)
    if filtres.date_fin:
        qs = qs.filter(commande__date__date__lte=filtres.date_fin)

    return qs.order_by("-commande__date")


def calculer_kpis_ventes(qs: QuerySet[LigneCommande]) -> dict:
    """KPIs affichés au-dessus du tableau. `qs` doit être NON tronqué (pas de pagination)."""
    agg = qs.aggregate(
        quantite_totale=Coalesce(Sum("quantite"), 0),
        montant_total=Coalesce(Sum("sous_total"), Value(Decimal("0"), output_field=DecimalField(max_digits=14, decimal_places=2))),
    )
    # `.order_by()` (sans argument) efface le tri hérité de la queryset :
    # sur PostgreSQL, `SELECT DISTINCT` exige que les colonnes du ORDER BY
    # figurent dans la liste sélectionnée, ce qui casserait cette requête
    # (elle ne sélectionne que `commande_id`) si le tri par date restait actif.
    agg["nombre_ventes"] = qs.order_by().values("commande_id").distinct().count()
    return agg