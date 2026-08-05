"""Agrégations pour les tableaux de bord (EF-12), consommées par Chart.js.

Fichier séparé des vues (comme products/services.py, sales/services.py) :
``admin_dashboard.py`` ne fait qu'orchestrer *quelle* agrégation appeler
selon le rôle/le périmètre, jamais *comment* elle est calculée. Toutes les
fonctions ici renvoient des structures déjà prêtes à être sérialisées en
JSON pour Chart.js (``{"labels": [...], "data": [...]}``), afin que les
templates n'aient qu'à faire ``{{ ... |json_script:"..." }}``.

Convention adoptée pour les statuts d'une Commande (EF-7.5) dans ces
agrégations :
- Le **chiffre d'affaires** (CA) ne compte que les ventes ``TERMINEE`` :
  une vente ``REMBOURSEE`` a rendu l'argent au client, elle ne doit plus
  compter comme revenu encaissé.
- Le **nombre de ventes/transactions** compte ``TERMINEE`` ET
  ``REMBOURSEE`` (une transaction a bien eu lieu), mais jamais
  ``ANNULEE`` (jamais finalisée) ni ``EN_ATTENTE``.
- Les KPIs de stock (valeur du stock, alertes stock bas) sont un état
  courant, indépendant de la période sélectionnée sur le dashboard.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.db.models import Count, DecimalField, F, QuerySet, Sum
from django.db.models.functions import Coalesce, TruncDate, TruncWeek
from django.http import HttpRequest
from django.utils import timezone
from django.utils.dateparse import parse_date

from general.enums import CommandeStatut, ModePaiement
from general.models import Agence
from products.models import ProduitAgence
from sales.models import Commande, LigneCommande

PERIODES_VALIDES = {"jour", "7j", "30j", "mois", "tout", "personnalise"}
STATUTS_TRANSACTION = [CommandeStatut.TERMINEE, CommandeStatut.REMBOURSEE]


@dataclass
class Periode:
    """Bornes de dates résolues pour le filtre du dashboard (``None`` = pas de borne)."""

    debut: Optional[date]
    fin: Optional[date]
    cle: str
    label: str


def resoudre_periode(request: HttpRequest) -> Periode:
    """Lit ``?periode=`` (+ ``date_debut``/``date_fin`` si "personnalise") depuis la requête.

    Retombe sur "30j" si le paramètre est absent ou invalide, plutôt que de
    lever une erreur — un filtre mal formé ne doit jamais casser le
    dashboard.
    """
    cle = request.GET.get("periode", "30j")
    if cle not in PERIODES_VALIDES:
        cle = "30j"

    aujourdhui = timezone.localdate()

    if cle == "jour":
        return Periode(aujourdhui, aujourdhui, cle, "Aujourd'hui")
    if cle == "7j":
        return Periode(aujourdhui - timedelta(days=6), aujourdhui, cle, "7 derniers jours")
    if cle == "mois":
        return Periode(aujourdhui.replace(day=1), aujourdhui, cle, "Ce mois-ci")
    if cle == "tout":
        return Periode(None, None, cle, "Depuis le début")
    if cle == "personnalise":
        debut = parse_date(request.GET.get("date_debut", "") or "") or (aujourdhui - timedelta(days=30))
        fin = parse_date(request.GET.get("date_fin", "") or "") or aujourdhui
        if debut > fin:
            debut, fin = fin, debut
        return Periode(debut, fin, cle, "Période personnalisée")

    # "30j" (défaut)
    return Periode(aujourdhui - timedelta(days=29), aujourdhui, "30j", "30 derniers jours")


def appliquer_periode(commandes_qs: QuerySet[Commande], periode: Periode) -> QuerySet[Commande]:
    """Filtre un queryset de Commande sur les bornes résolues (aucune borne = tout l'historique)."""
    if periode.debut is not None:
        commandes_qs = commandes_qs.filter(date__date__gte=periode.debut)
    if periode.fin is not None:
        commandes_qs = commandes_qs.filter(date__date__lte=periode.fin)
    return commandes_qs


def calculer_kpis_ventes(commandes_periode: QuerySet[Commande]) -> Dict[str, Any]:
    """CA, nombre de ventes et panier moyen sur la période déjà filtrée."""
    ca_agg = commandes_periode.filter(statut=CommandeStatut.TERMINEE).aggregate(
        ca=Coalesce(Sum("total"), Decimal("0"))
    )
    transactions = commandes_periode.filter(statut__in=STATUTS_TRANSACTION)
    nombre_ventes = transactions.count()
    panier_moyen = (ca_agg["ca"] / nombre_ventes) if nombre_ventes else Decimal("0")

    produits_vendus = LigneCommande.objects.filter(
        commande__in=commandes_periode.filter(statut=CommandeStatut.TERMINEE)
    ).aggregate(total=Coalesce(Sum("quantite"), 0))["total"]

    return {
        "ca": ca_agg["ca"],
        "nombre_ventes": nombre_ventes,
        "panier_moyen": panier_moyen,
        "produits_vendus": produits_vendus,
    }


def serie_ca_dans_le_temps(commandes_periode: QuerySet[Commande], periode: Periode) -> Dict[str, List[Any]]:
    """CA au jour le jour (ou à la semaine si la période dépasse ~60 jours), pour un graphique en ligne."""
    granularite_hebdo = False
    if periode.debut and periode.fin:
        granularite_hebdo = (periode.fin - periode.debut).days > 60
    elif periode.cle == "tout":
        granularite_hebdo = True

    trunc = TruncWeek("date") if granularite_hebdo else TruncDate("date")
    lignes = (
        commandes_periode.filter(statut=CommandeStatut.TERMINEE)
        .annotate(periode_jour=trunc)
        .values("periode_jour")
        .annotate(ca=Sum("total"))
        .order_by("periode_jour")
    )
    fmt = "%d/%m" if not granularite_hebdo else "sem. %W"
    labels = [ligne["periode_jour"].strftime(fmt) for ligne in lignes if ligne["periode_jour"]]
    data = [float(ligne["ca"]) for ligne in lignes]
    return {"labels": labels, "data": data}


def ventes_par_mode_paiement(commandes_periode: QuerySet[Commande]) -> Dict[str, List[Any]]:
    lignes = (
        commandes_periode.filter(statut=CommandeStatut.TERMINEE)
        .values("mode_paiement")
        .annotate(ca=Sum("total"))
        .order_by("-ca")
    )
    labels_map = dict(ModePaiement.choices)
    labels = [labels_map.get(ligne["mode_paiement"], ligne["mode_paiement"]) for ligne in lignes]
    data = [float(ligne["ca"]) for ligne in lignes]
    return {"labels": labels, "data": data}


def top_produits(commandes_periode: QuerySet[Commande], limite: int = 5) -> Dict[str, List[Any]]:
    lignes = (
        LigneCommande.objects.filter(commande__in=commandes_periode.filter(statut=CommandeStatut.TERMINEE))
        .values("produit__nom")
        .annotate(ca=Sum("sous_total"))
        .order_by("-ca")[:limite]
    )
    return {"labels": [l["produit__nom"] for l in lignes], "data": [float(l["ca"]) for l in lignes]}


def ventes_par_categorie(commandes_periode: QuerySet[Commande], limite: int = 6) -> Dict[str, List[Any]]:
    lignes = (
        LigneCommande.objects.filter(commande__in=commandes_periode.filter(statut=CommandeStatut.TERMINEE))
        .values("produit__categorie__nom")
        .annotate(ca=Sum("sous_total"))
        .order_by("-ca")[:limite]
    )
    return {
        "labels": [l["produit__categorie__nom"] or "Sans catégorie" for l in lignes],
        "data": [float(l["ca"]) for l in lignes],
    }


def ca_par_agence(commandes_periode: QuerySet[Commande], limite: int = 10) -> Dict[str, List[Any]]:
    """Comparaison du CA entre agences (dashboard Admin uniquement)."""
    lignes = (
        commandes_periode.filter(statut=CommandeStatut.TERMINEE)
        .values("agence__nom")
        .annotate(ca=Sum("total"))
        .order_by("-ca")[:limite]
    )
    return {"labels": [l["agence__nom"] for l in lignes], "data": [float(l["ca"]) for l in lignes]}


def performance_caissiers(commandes_periode: QuerySet[Commande], limite: int = 10) -> Dict[str, List[Any]]:
    """CA par caissier au sein d'une agence (dashboard Responsable d'agence)."""
    lignes = (
        commandes_periode.filter(statut=CommandeStatut.TERMINEE)
        .values("caissier__id", "caissier__first_name", "caissier__last_name", "caissier__username")
        .annotate(ca=Sum("total"), nombre_ventes=Count("id"))
        .order_by("-ca")[:limite]
    )
    labels = []
    for l in lignes:
        nom_complet = f"{l['caissier__first_name']} {l['caissier__last_name']}".strip()
        labels.append(nom_complet or l["caissier__username"])
    return {
        "labels": labels,
        "data": [float(l["ca"]) for l in lignes],
        "nombre_ventes": [l["nombre_ventes"] for l in lignes],
    }


def ca_par_agence_map(commandes_periode: QuerySet[Commande]) -> Dict[Any, Decimal]:
    """Comme ``ca_par_agence``, mais indexé par ``agence_id`` (pour un tableau récap
    agence par agence, évite de dépendre du nom pour rapprocher les lignes)."""
    lignes = (
        commandes_periode.filter(statut=CommandeStatut.TERMINEE)
        .values("agence_id")
        .annotate(ca=Sum("total"))
    )
    return {l["agence_id"]: l["ca"] for l in lignes}


def stock_bas_par_agence_map() -> Dict[Any, int]:
    """Nombre de fiches ProduitAgence en alerte stock bas, par agence (état courant)."""
    lignes = (
        ProduitAgence.objects.filter(actif=True, stock_quantite__lte=F("seuil_alerte"))
        .values("agence_id")
        .annotate(n=Count("id"))
    )
    return {l["agence_id"]: l["n"] for l in lignes}


def produits_stock_bas(agences_qs: Optional[QuerySet[Agence]] = None, agence: Optional[Agence] = None):
    """Fiches ProduitAgence en alerte stock bas (état courant, hors filtre de période).

    Fournir soit ``agences_qs`` (dashboard multi-agences), soit ``agence``
    (dashboard d'une agence précise) — jamais les deux. Renvoie le queryset
    COMPLET (non tronqué) : l'appelant décide lui-même s'il veut
    ``.count()`` pour un KPI et/ou ``[:n]`` pour un tableau, sans risquer
    d'appeler ``.count()`` sur un queryset déjà tronqué (ce qui recompterait
    seulement les lignes affichées).
    """
    qs = ProduitAgence.objects.select_related("produit", "agence").filter(
        actif=True, stock_quantite__lte=F("seuil_alerte")
    )
    if agence is not None:
        qs = qs.filter(agence=agence)
    elif agences_qs is not None:
        qs = qs.filter(agence__in=agences_qs)
    return qs.order_by("stock_quantite")


def valeur_stock(agences_qs: Optional[QuerySet[Agence]] = None, agence: Optional[Agence] = None) -> Decimal:
    """Valeur d'achat du stock actuellement détenu (quantité x prix d'achat du produit)."""
    qs = ProduitAgence.objects.filter(actif=True)
    if agence is not None:
        qs = qs.filter(agence=agence)
    elif agences_qs is not None:
        qs = qs.filter(agence__in=agences_qs)

    total = qs.aggregate(
        valeur=Coalesce(
            Sum(F("stock_quantite") * F("produit__prix_achat"), output_field=DecimalField(max_digits=14, decimal_places=2)),
            Decimal("0"),
        )
    )
    return total["valeur"]