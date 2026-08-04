"""Transfert de stock entre agences (EF-5).

Fichier séparé suivant votre convention actuelle (un fichier de vues par
fonctionnalité). Version volontairement SIMPLE par rapport au cycle de
vie complet que le modèle TransfertStock permettrait (EN_ATTENTE ->
APPROUVE -> TERMINE) : dès la soumission du formulaire, chaque produit se
transfère immédiatement — la quantité est déduite de l'agence source et
ajoutée à l'agence destination, et la fiche TransfertStock est enregistrée
directement au statut TERMINE, avec ``approuve_par`` = la même personne
que ``demande_par``. Si vous voulez réintroduire une étape d'approbation
séparée plus tard, c'est ce fichier qu'il faudra faire évoluer.

Un transfert peut porter sur PLUSIEURS produits à la fois : on choisit
d'abord l'agence source et l'agence destination, puis on recherche et
ajoute des produits à une liste (comme StockPriceCreateView), la
recherche étant limitée aux produits réellement disponibles (stock > 0)
dans l'agence source choisie — pas tout le catalogue. Si l'agence
destination n'a pas encore ce produit, sa fiche stock/prix y est créée à
la volée (produit "non enregistré" dans cette agence -> il l'est après le
transfert).
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Q, QuerySet
from django.http import HttpRequest, JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import ListView, TemplateView

from general.enums import TransfertStatut
from products.forms import TransfertStockForm
from products.models import ProduitAgence, TransfertStock
from products.services import get_agences_autorisees, get_agences_visibles
from products.views.stock_views import StockAccessMixin


def _to_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _transferts_visibles_par(user) -> QuerySet[TransfertStock]:
    """Transferts où l'agence de ``user`` intervient, comme source OU destination.

    Utilisé à la fois par le mini-historique de la page de création et par
    ``TransfertListView`` : un Responsable doit voir dans son historique
    les transferts qu'il a envoyés ET ceux que son agence a reçus (EF-1.3,
    EF-13.3). ``get_agences_visibles`` (pas ``get_agences_autorisees``) car
    on veut aussi retrouver les transferts impliquant une agence
    entre-temps désactivée.
    """
    agences_visibles = get_agences_visibles(user)
    return TransfertStock.objects.filter(
        Q(agence_source__in=agences_visibles) | Q(agence_destination__in=agences_visibles)
    )


class _ProduitSansStock(Exception):
    """Signal interne : l'agence source n'a aucune fiche stock/prix pour ce produit."""


class _StockInsuffisant(Exception):
    """Signal interne : stock source insuffisant, transaction annulée."""

    def __init__(self, disponible: int) -> None:
        super().__init__(disponible)
        self.disponible = disponible


class TransfertProduitRechercheApiView(LoginRequiredMixin, StockAccessMixin, View):
    """Produits réellement disponibles (stock > 0) dans une agence source, en JSON.

    Contrairement à la recherche de la page Stock & prix (qui porte sur
    tout le catalogue actif), celle-ci ne renvoie QUE les produits déjà en
    stock dans l'agence choisie comme source — on ne peut pas transférer
    ce qui n'y est pas. ``agence_id`` doit faire partie des agences
    autorisées pour l'utilisateur courant (revalidé ici, jamais fait
    confiance au client) ; sinon, résultats vides plutôt qu'une erreur qui
    fuiterait de l'information.
    """

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> JsonResponse:
        agence_id = request.GET.get("agence_id", "").strip()
        q = request.GET.get("q", "").strip()

        agence_ids_autorises = set(
            str(pk) for pk in get_agences_autorisees(request.user).values_list("pk", flat=True)
        )
        if not agence_id or agence_id not in agence_ids_autorises:
            return JsonResponse({"results": []})

        stocks_qs = (
            ProduitAgence.objects.select_related("produit")
            .filter(agence_id=agence_id, actif=True, stock_quantite__gt=0, produit__actif=True)
        )
        if q:
            stocks_qs = stocks_qs.filter(Q(produit__nom__icontains=q) | Q(produit__sku__icontains=q))
        stocks = stocks_qs.order_by("produit__nom")[:20]

        results = [
            {
                "produit_id": str(s.produit_id),
                "nom": s.produit.nom,
                "sku": s.produit.sku,
                "stock_disponible": s.stock_quantite,
            }
            for s in stocks
        ]
        return JsonResponse({"results": results})


class TransfertCreateView(LoginRequiredMixin, StockAccessMixin, TemplateView):
    """Transfert d'un ou plusieurs produits entre deux agences + historique récent (EF-5).

    Combine, comme les pages d'import de catégories/produits, un
    formulaire (POST) et un historique récent (GET) sur une seule page.
    Les produits et quantités sont saisis via une interface "panier" (JS,
    voir ``entries_json``), comme sur StockPriceCreateView : chaque ligne
    est traitée indépendamment (une ligne en échec — stock insuffisant,
    produit invalide — n'annule pas les autres), mais les fiches
    TransfertStock elles-mêmes sont créées en un seul ``bulk_create``.

    Accès : Admin (n'importe quelle agence source active) ou Responsable
    d'agence (uniquement SA propre agence comme source — voir
    ``TransfertStockForm``, qui restreint le queryset du champ, revalidé
    par Django lui-même côté serveur, pas seulement masqué côté client).
    """

    template_name = "dashboard/pages/admin/products/transfer/transfert_form.html"

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.setdefault("form", TransfertStockForm(user=self.request.user))
        agences_autorisees = get_agences_autorisees(self.request.user)
        context["a_une_agence_source"] = agences_autorisees.exists()
        context["transferts"] = (
            _transferts_visibles_par(self.request.user)
            .select_related("produit", "agence_source", "agence_destination", "demande_par")
            .order_by("-created_at")[:10]
        )
        return context

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any):
        form = TransfertStockForm(request.POST, user=request.user)

        if not form.is_valid():
            context = self.get_context_data(form=form)
            return self.render_to_response(context)

        source = form.cleaned_data["agence_source"]
        destination = form.cleaned_data["agence_destination"]

        try:
            entries = json.loads(request.POST.get("entries_json") or "[]")
        except (TypeError, ValueError):
            entries = []

        if not isinstance(entries, list) or not entries:
            messages.warning(request, _("Sélectionnez au moins un produit à transférer."))
            context = self.get_context_data(form=form)
            return self.render_to_response(context)

        # Un même produit ajouté deux fois au panier : on additionne les
        # quantités plutôt que de traiter deux lignes séparées pour la
        # même paire (produit, agence).
        quantites_par_produit: Dict[str, int] = {}
        ignores_invalide = 0
        for entry in entries:
            produit_id = str(entry.get("produit_id") or "")
            quantite = _to_int(entry.get("quantite"))
            if not produit_id or quantite is None or quantite <= 0:
                ignores_invalide += 1
                continue
            quantites_par_produit[produit_id] = quantites_par_produit.get(produit_id, 0) + quantite

        transferts_a_creer: List[TransfertStock] = []
        transferes = 0
        ignores_stock_insuffisant = 0

        for produit_id, quantite in quantites_par_produit.items():
            try:
                with transaction.atomic():
                    try:
                        stock_source = ProduitAgence.objects.select_for_update().get(
                            produit_id=produit_id, agence=source
                        )
                    except ProduitAgence.DoesNotExist:
                        raise _ProduitSansStock

                    if stock_source.stock_quantite < quantite:
                        raise _StockInsuffisant(stock_source.stock_quantite)

                    stock_source.stock_quantite -= quantite
                    stock_source.save(update_fields=["stock_quantite", "updated_at"])

                    # Si l'agence destination n'a pas encore ce produit (il
                    # n'y est pas "enregistré"), on lui crée sa fiche
                    # stock/prix à la volée, avec le prix de vente
                    # actuellement pratiqué par la source comme valeur de
                    # départ (ajustable ensuite depuis Stock & prix).
                    stock_destination, _created = ProduitAgence.objects.select_for_update().get_or_create(
                        produit_id=produit_id,
                        agence=destination,
                        defaults={"prix_vente": stock_source.prix_vente, "stock_quantite": 0},
                    )
                    stock_destination.stock_quantite += quantite
                    stock_destination.save(update_fields=["stock_quantite", "updated_at"])
            except _ProduitSansStock:
                ignores_invalide += 1
                continue
            except _StockInsuffisant:
                ignores_stock_insuffisant += 1
                continue

            transferts_a_creer.append(
                TransfertStock(
                    produit_id=produit_id,
                    agence_source=source,
                    agence_destination=destination,
                    quantite=quantite,
                    statut=TransfertStatut.TERMINE,
                    demande_par=request.user,
                    approuve_par=request.user,
                    date_transfert=timezone.now(),
                )
            )
            transferes += 1

        if transferts_a_creer:
            TransfertStock.objects.bulk_create(transferts_a_creer)

        if transferes:
            messages.success(
                request,
                _("%(n)d produit(s) transféré(s) de %(src)s vers %(dst)s.")
                % {"n": transferes, "src": source.nom, "dst": destination.nom},
            )
        if ignores_stock_insuffisant:
            messages.warning(
                request,
                _("%(n)d produit(s) ignoré(s) : stock insuffisant dans l'agence source.")
                % {"n": ignores_stock_insuffisant},
            )
        if ignores_invalide:
            messages.warning(
                request,
                _("%(n)d ligne(s) ignorée(s) : produit introuvable dans l'agence source ou quantité invalide.")
                % {"n": ignores_invalide},
            )
        if not transferes and not ignores_stock_insuffisant and not ignores_invalide:
            messages.warning(request, _("Aucune ligne valide à transférer."))

        return redirect("products:transfert_create")


class TransfertListView(LoginRequiredMixin, StockAccessMixin, ListView):
    """Historique complet, paginé, des transferts de stock (EF-5, EF-13.3).

    ``select_related`` sur produit/agence_source/agence_destination/
    demande_par : évite une requête par ligne affichée (EF-13.1). Montre
    les transferts où l'agence de l'utilisateur est source OU destination
    (``_transferts_visibles_par``), pas seulement ceux qu'il a envoyés —
    un Responsable doit aussi voir ce que son agence a reçu.
    """

    model = TransfertStock
    template_name = "dashboard/pages/admin/products/transfer/transfert_list.html"
    context_object_name = "transferts"
    paginate_by = 20

    def get_queryset(self) -> QuerySet[TransfertStock]:
        qs = (
            _transferts_visibles_par(self.request.user)
            .select_related("produit", "agence_source", "agence_destination", "demande_par")
            .order_by("-created_at")
        )

        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(Q(produit__nom__icontains=q) | Q(produit__sku__icontains=q))

        agence_id = self.request.GET.get("agence", "").strip()
        if agence_id:
            qs = qs.filter(Q(agence_source_id=agence_id) | Q(agence_destination_id=agence_id))

        return qs

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["q"] = self.request.GET.get("q", "")
        context["agence_id"] = self.request.GET.get("agence", "")
        context["agences_visibles"] = get_agences_visibles(self.request.user).order_by("nom")
        return context