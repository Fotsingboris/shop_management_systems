"""Saisie groupée du stock et du prix de vente par agence (EF-4.2, EF-4.3).

Fichier séparé de ``category_views.py``/``product_views.py`` en suivant
votre convention actuelle (un fichier de vues par fonctionnalité).

Contrairement aux CRUD Catégorie/Produit, cette page n'est PAS réservée à
l'Admin : un Responsable d'agence doit pouvoir configurer le stock/prix de
SA propre agence (EF-9.3), mais pas des autres. ``get_agences_autorisees``
centralise cette règle et est utilisée à la fois pour l'affichage (GET) et
pour la revalidation côté serveur (POST) — on ne fait jamais confiance à
l'agence envoyée par le client, même si le formulaire ne montre que les
agences autorisées.
"""
from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import F, Q, QuerySet
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import ListView, TemplateView

from general.models import Agence
from products.forms import StockAjustementForm
from products.models import Produit, ProduitAgence


class StockAccessMixin(UserPassesTestMixin):
    """Admin (toutes agences) ou Responsable d'agence (la sienne uniquement) (EF-9.2, EF-9.3)."""

    def test_func(self) -> bool:
        user = self.request.user
        return getattr(user, "is_admin", False) or getattr(user, "is_responsable_agence", False)


def get_agences_autorisees(user) -> QuerySet[Agence]:
    """Agences actives que ``user`` a le droit de configurer.

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
    """Agences dont ``user`` peut CONSULTER le stock/prix, pour la liste (EF-1.3, EF-13.3).

    Différent de ``get_agences_autorisees()`` (qui ne sert qu'à choisir où
    AJOUTER du stock, donc uniquement des agences actives) : une agence
    désactivée "reste visible dans l'historique et les rapports" (EF-1.3),
    donc la liste ne filtre pas sur ``actif``.
    """
    if getattr(user, "is_admin", False):
        return Agence.objects.all()
    if getattr(user, "is_responsable_agence", False) and user.agence_id:
        return Agence.objects.filter(pk=user.agence_id)
    return Agence.objects.none()


def _to_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_decimal(value: Any) -> Optional[Decimal]:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).strip().replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


class ProduitRechercheApiView(LoginRequiredMixin, StockAccessMixin, View):
    """Recherche de produits pour la page stock/prix, en JSON (EF-4.2).

    Pour chaque produit trouvé, renvoie aussi, pour les agences (parmi
    celles autorisées pour l'utilisateur courant) qui ont déjà une fiche
    ProduitAgence, l'identifiant de cette fiche — calculé en une seule
    requête groupée plutôt qu'une requête par produit affiché (EF-13.1).
    La page affiche alors un lien « Modifier » vers StockUpdateView à la
    place d'une case à saisir qui serait de toute façon ignorée à
    l'enregistrement (le stock peut être ajouté à tout moment : on ne veut
    pas d'impasse quand un produit est déjà configuré partout).
    """

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> JsonResponse:
        q = request.GET.get("q", "").strip()
        agence_ids = list(get_agences_autorisees(request.user).values_list("pk", flat=True))

        produits_qs = Produit.objects.filter(actif=True)
        if q:
            produits_qs = produits_qs.filter(Q(nom__icontains=q) | Q(sku__icontains=q))
        produits = list(produits_qs.order_by("nom")[:20])

        # produit_id -> {agence_id: stock_id} : mapping vers la fiche
        # ProduitAgence existante, pour construire un lien de modification.
        configurees_par_produit: Dict[Any, Dict[str, str]] = {p.pk: {} for p in produits}
        produit_ids = list(configurees_par_produit.keys())
        if produit_ids and agence_ids:
            paires = ProduitAgence.objects.filter(
                produit_id__in=produit_ids, agence_id__in=agence_ids
            ).values_list("produit_id", "agence_id", "id")
            for produit_id, agence_id, stock_id in paires:
                configurees_par_produit.setdefault(produit_id, {})[str(agence_id)] = str(stock_id)

        results = [
            {
                "id": str(p.pk),
                "nom": p.nom,
                "sku": p.sku,
                "prix_vente_defaut": str(p.prix_vente_defaut),
                "agences_configurees": configurees_par_produit.get(p.pk, {}),
            }
            for p in produits
        ]
        return JsonResponse({"results": results})


class StockPriceCreateView(LoginRequiredMixin, StockAccessMixin, TemplateView):
    """Saisie groupée du stock et du prix de vente par agence (EF-4.2, EF-4.3).

    Page pensée comme un petit "panier" côté client : on recherche des
    produits, on les ajoute à une liste, on saisit quantité + prix de
    vente pour chaque agence autorisée (le prix peut différer d'une
    agence à l'autre), puis un seul POST déclenche un unique
    ``ProduitAgence.objects.bulk_create(...)`` plutôt que de créer les
    fiches une par une.

    Cette page sert uniquement à INITIALISER le stock/prix d'un produit
    dans une agence qui ne l'a pas encore (ProduitAgence a une contrainte
    d'unicité (produit, agence)) : une paire déjà existante est ignorée
    côté serveur plutôt que de faire échouer tout le lot, et signalée
    "Déjà configuré" côté client pour éviter de faire saisir une valeur
    qui serait de toute façon ignorée.
    """

    template_name = "dashboard/pages/admin/products/stock/stock_form.html"

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        agences = list(get_agences_autorisees(self.request.user))
        context["agences"] = agences
        context["agences_json"] = json.dumps([{"id": str(a.pk), "nom": a.nom} for a in agences])
        return context

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any):
        agences_autorisees = get_agences_autorisees(request.user)
        agence_ids_autorises = {str(pk) for pk in agences_autorisees.values_list("pk", flat=True)}

        try:
            entries = json.loads(request.POST.get("entries_json") or "[]")
        except (TypeError, ValueError):
            entries = []

        if not isinstance(entries, list) or not entries:
            messages.warning(
                request,
                _("Aucune ligne à enregistrer : sélectionnez au moins un produit et renseignez quantité et prix."),
            )
            return redirect("products:stock_create")

        produit_ids = {str(e.get("produit_id")) for e in entries if e.get("produit_id")}
        existants = {
            (str(produit_id), str(agence_id))
            for produit_id, agence_id in ProduitAgence.objects.filter(
                produit_id__in=produit_ids
            ).values_list("produit_id", "agence_id")
        }

        a_creer: List[ProduitAgence] = []
        crees = 0
        ignores_deja_existant = 0
        ignores_non_autorise = 0
        ignores_invalide = 0

        for entry in entries:
            produit_id = str(entry.get("produit_id") or "")
            agence_id = str(entry.get("agence_id") or "")
            if not produit_id or not agence_id:
                ignores_invalide += 1
                continue

            if agence_id not in agence_ids_autorises:
                # Jamais confiance dans l'agence envoyée par le client : un
                # Responsable d'agence ne doit configurer QUE sa propre
                # agence, même s'il modifie la requête à la main (EF-9.3).
                ignores_non_autorise += 1
                continue

            pair = (produit_id, agence_id)
            if pair in existants:
                ignores_deja_existant += 1
                continue

            quantite = _to_int(entry.get("quantite"))
            prix_vente = _to_decimal(entry.get("prix_vente"))
            if quantite is None or quantite < 0 or prix_vente is None or prix_vente <= 0:
                ignores_invalide += 1
                continue

            a_creer.append(
                ProduitAgence(
                    produit_id=produit_id,
                    agence_id=agence_id,
                    stock_quantite=quantite,
                    prix_vente=prix_vente,
                )
            )
            existants.add(pair)  # évite un doublon si la même paire apparaît deux fois dans le payload
            crees += 1

        if a_creer:
            ProduitAgence.objects.bulk_create(a_creer)

        if crees:
            messages.success(request, _("%(n)d fiche(s) stock/prix créée(s).") % {"n": crees})
        if ignores_deja_existant:
            messages.info(
                request,
                _("%(n)d ligne(s) ignorée(s) : déjà configurée(s) pour cette agence.") % {"n": ignores_deja_existant},
            )
        if ignores_non_autorise:
            messages.warning(
                request, _("%(n)d ligne(s) ignorée(s) : agence non autorisée.") % {"n": ignores_non_autorise}
            )
        if ignores_invalide:
            messages.warning(
                request, _("%(n)d ligne(s) ignorée(s) : quantité ou prix invalide.") % {"n": ignores_invalide}
            )
        if not crees and not ignores_deja_existant and not ignores_non_autorise and not ignores_invalide:
            messages.warning(request, _("Aucune ligne valide à enregistrer."))

        return redirect("products:stock_create")


class StockListView(LoginRequiredMixin, StockAccessMixin, ListView):
    """Liste paginée de tout le stock/prix par agence déjà configuré (EF-4, EF-13.3).

    ``select_related`` sur produit/produit__categorie/agence : évite une
    requête par ligne affichée (EF-13.1). Scope par rôle comme la page
    d'ajout (``get_agences_visibles``), mais sans exclure les agences
    désactivées : leur historique doit rester consultable (EF-1.3).
    """

    model = ProduitAgence
    template_name = "dashboard/pages/admin/products/stock/stock_list.html"
    context_object_name = "stocks"
    paginate_by = 20

    def get_queryset(self) -> QuerySet[ProduitAgence]:
        agences_visibles = get_agences_visibles(self.request.user)
        qs = (
            ProduitAgence.objects.select_related("produit", "produit__categorie", "agence")
            .filter(agence__in=agences_visibles)
            .order_by("produit__nom", "agence__nom")
        )

        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(Q(produit__nom__icontains=q) | Q(produit__sku__icontains=q))

        agence_id = self.request.GET.get("agence", "").strip()
        if agence_id:
            qs = qs.filter(agence_id=agence_id)

        if self.request.GET.get("bas") == "1":
            # Stock au ou sous le seuil d'alerte (EF-4.4) : comparaison entre
            # deux colonnes de la même ligne via F(), donc toujours en SQL,
            # pas en Python après récupération des lignes.
            qs = qs.filter(stock_quantite__lte=F("seuil_alerte"))

        return qs

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["q"] = self.request.GET.get("q", "")
        context["agence_id"] = self.request.GET.get("agence", "")
        context["bas"] = self.request.GET.get("bas", "")
        context["agences_visibles"] = get_agences_visibles(self.request.user).order_by("nom")
        # Détermine quelles lignes affichent un lien « Modifier » : on ne
        # permet d'ajuster que les fiches d'une agence active et autorisée
        # (même règle que la création), même si la liste elle-même montre
        # aussi les agences désactivées à titre d'historique (EF-1.3).
        context["agences_editables_ids"] = {
            str(pk) for pk in get_agences_autorisees(self.request.user).values_list("pk", flat=True)
        }
        return context


class StockUpdateView(LoginRequiredMixin, StockAccessMixin, View):
    """Réapprovisionne / corrige une fiche ProduitAgence déjà existante (EF-4.2, EF-4.3, EF-4.4).

    Contrairement à StockPriceCreateView (qui initialise une agence qui
    n'a pas encore ce produit via bulk_create), cette vue édite une fiche
    déjà là : la quantité saisie s'AJOUTE au stock actuel (réappro ou
    correction, positive ou négative) plutôt que de le remplacer, tandis
    que le prix de vente et le seuil d'alerte sont bien remplacés
    directement. Accessible pour ajuster le stock "à tout moment", pas
    seulement à la création.
    """

    template_name = "dashboard/pages/admin/products/stock/stock_update_form.html"

    def _get_object(self, request: HttpRequest, pk) -> ProduitAgence:
        # Même périmètre que la création : agence active et autorisée pour
        # ce rôle, jamais une agence appartenant à quelqu'un d'autre, même
        # si l'URL est modifiée à la main (EF-9.3).
        agences_autorisees = get_agences_autorisees(request.user)
        return get_object_or_404(
            ProduitAgence.objects.select_related("produit", "agence"),
            pk=pk,
            agence__in=agences_autorisees,
        )

    def get(self, request: HttpRequest, pk, *args: Any, **kwargs: Any):
        stock = self._get_object(request, pk)
        form = StockAjustementForm(
            initial={
                "quantite_a_ajouter": 0,
                "prix_vente": stock.prix_vente,
                "seuil_alerte": stock.seuil_alerte,
            }
        )
        return render(request, self.template_name, {"stock": stock, "form": form})

    def post(self, request: HttpRequest, pk, *args: Any, **kwargs: Any):
        stock = self._get_object(request, pk)
        form = StockAjustementForm(request.POST)
        if form.is_valid():
            delta = form.cleaned_data["quantite_a_ajouter"]
            nouveau_total = stock.stock_quantite + delta
            if nouveau_total < 0:
                form.add_error(
                    "quantite_a_ajouter",
                    _("Le stock ne peut pas devenir négatif (stock actuel : %(n)d).") % {"n": stock.stock_quantite},
                )
            else:
                stock.stock_quantite = nouveau_total
                stock.prix_vente = form.cleaned_data["prix_vente"]
                stock.seuil_alerte = form.cleaned_data["seuil_alerte"]
                stock.save(update_fields=["stock_quantite", "prix_vente", "seuil_alerte", "updated_at"])
                messages.success(
                    request,
                    _("Stock mis à jour : %(produit)s @ %(agence)s (nouveau stock : %(n)d).")
                    % {"produit": stock.produit.nom, "agence": stock.agence.nom, "n": stock.stock_quantite},
                )
                return redirect("products:stock_list")

        return render(request, self.template_name, {"stock": stock, "form": form})