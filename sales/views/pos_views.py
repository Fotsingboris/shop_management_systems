"""Point de vente (POS) : encaissement, historique et gestion des ventes (EF-6 à EF-9).

Fichier séparé par fonctionnalité, comme products/stock_views.py et
products/transfer_views.py. Contient volontairement TOUT le cycle "CRUD"
demandé pour le POS :

- Create  : ``CommandeCreateView`` (l'écran de caisse lui-même).
- Read    : ``CommandeListView`` (historique) et ``CommandeDetailView``
  (détail d'une vente / reçu).
- Update  : ``CommandeStatutUpdateView`` — annuler ou rembourser une vente
  terminée. Il n'y a PAS de suppression pure : une vente est une pièce
  comptable (des LigneCommande protègent les Produit via PROTECT), donc on
  ne détruit jamais une vente — on change son statut, ce qui recrédite le
  stock. C'est l'équivalent, pour les ventes, du champ ``actif`` utilisé
  ailleurs pour les agences/produits.

Deux API JSON alimentent l'interface "panier" en JS de la page de
création : recherche de produits (limitée aux produits réellement en stock
dans l'agence du caissier connecté) et recherche de clients par
téléphone/nom.
"""
from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.db.models import Q, QuerySet
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from general.enums import CommandeStatut
from products.models import ProduitAgence
from products.services import get_agences_autorisees, get_agences_visibles, get_categories_actives
from sales.forms import CommandeForm
from sales.models import Client, Commande, LigneCommande
from sales.services import get_commandes_visibles


def _to_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class POSAccessMixin(UserPassesTestMixin):
    """N'importe quel rôle reconnu peut encaisser : Admin, Responsable
    d'agence ou Caissier (pas seulement ce dernier). ``limit_choices_to``
    sur ``Commande.caissier`` dans le modèle ne fait que suggérer les
    Caissiers en premier dans un futur formulaire d'admin Django : ce n'est
    pas une contrainte imposée en base, donc rien n'empêche d'y stocker
    l'utilisateur (quel que soit son rôle) qui a réellement encaissé la
    vente.
    """

    def test_func(self) -> bool:
        user = self.request.user
        return (
            getattr(user, "is_admin", False)
            or getattr(user, "is_responsable_agence", False)
            or getattr(user, "is_caissier", False)
        )


class CommandeGestionAccessMixin(UserPassesTestMixin):
    """Annuler/rembourser une vente est réservé à l'encadrement (EF-9.2, EF-9.3) :
    un Caissier ne doit pas pouvoir défaire sa propre vente pour maquiller
    sa caisse.
    """

    def test_func(self) -> bool:
        return getattr(self.request.user, "is_admin", False) or getattr(
            self.request.user, "is_responsable_agence", False
        )


class _StockInsuffisant(Exception):
    """Signal interne : stock insuffisant pour ce produit dans l'agence du caissier."""

    def __init__(self, nom: str, disponible: int) -> None:
        super().__init__(nom, disponible)
        self.nom = nom
        self.disponible = disponible


class _RemiseExcessive(Exception):
    """Signal interne : la remise dépasse le sous-total de la vente."""


class POSProduitRechercheApiView(LoginRequiredMixin, POSAccessMixin, View):
    """Produits réellement disponibles (stock > 0) dans l'agence de la vente, en JSON.

    Contrairement à la recherche "Stock & prix" (tout le catalogue actif),
    celle-ci ne renvoie que les produits déjà en stock dans l'agence
    concernée — on ne peut vendre que ce qui y est physiquement
    disponible.

    Pour un utilisateur rattaché à une agence fixe (Caissier, Responsable),
    l'agence n'est jamais lue depuis la requête : elle vient uniquement de
    ``request.user.agence_id``, impossible à falsifier côté client. Pour un
    Admin (sans agence propre, il en choisit une dans le formulaire), on
    accepte un ``agence_id`` en paramètre mais on le revalide contre
    ``get_agences_autorisees`` avant de l'utiliser — jamais fait confiance
    tel quel.
    """

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> JsonResponse:
        user = request.user
        if user.agence_id:
            agence_id = str(user.agence_id)
        else:
            agence_id = request.GET.get("agence_id", "").strip()
            agence_ids_autorises = set(
                str(pk) for pk in get_agences_autorisees(user).values_list("pk", flat=True)
            )
            if not agence_id or agence_id not in agence_ids_autorises:
                return JsonResponse({"results": []})

        q = request.GET.get("q", "").strip()
        categorie_id = request.GET.get("categorie_id", "").strip()

        stocks_qs = ProduitAgence.objects.select_related("produit", "produit__categorie").filter(
            agence_id=agence_id, actif=True, stock_quantite__gt=0, produit__actif=True
        )
        if q:
            stocks_qs = stocks_qs.filter(Q(produit__nom__icontains=q) | Q(produit__sku__icontains=q))
        if categorie_id:
            stocks_qs = stocks_qs.filter(produit__categorie_id=categorie_id)

        total = stocks_qs.count()
        stocks = stocks_qs.order_by("produit__nom")[:24]

        results = [
            {
                "produit_id": str(s.produit_id),
                "nom": s.produit.nom,
                "sku": s.produit.sku,
                "prix_vente": str(s.prix_vente),
                "stock_disponible": s.stock_quantite,
                "categorie": s.produit.categorie.nom if s.produit.categorie_id else "",
                "image_url": s.produit.image.url if s.produit.image else "",
            }
            for s in stocks
        ]
        return JsonResponse({"results": results, "total": total, "affiches": len(results)})


class ClientRechercheApiView(LoginRequiredMixin, POSAccessMixin, View):
    """Recherche de clients existants par téléphone ou nom, en JSON (EF-6.4).

    Sert à pré-remplir le formulaire de vente et à éviter de recréer un
    doublon quand le client existe déjà. Une recherche à 1 caractère
    renverrait trop de bruit : on exige au moins 2 caractères.
    """

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> JsonResponse:
        q = request.GET.get("q", "").strip()
        if len(q) < 2:
            return JsonResponse({"results": []})

        clients = Client.objects.filter(Q(telephone__icontains=q) | Q(nom__icontains=q)).order_by("nom")[:10]
        results = [{"id": str(c.id), "nom": c.nom, "telephone": c.telephone} for c in clients]
        return JsonResponse({"results": results})


class CommandeCreateView(LoginRequiredMixin, POSAccessMixin, TemplateView):
    """Écran de caisse : encaissement d'une vente, potentiellement multi-produits (EF-7).

    Combine, comme les autres écrans "panier" du projet, un GET (formulaire
    vide) et un POST (traitement). Chaque ligne du panier est vérifiée et
    décrémentée à l'intérieur d'une même transaction atomique avec
    ``select_for_update`` : soit toute la vente réussit, soit elle échoue
    entièrement (contrairement aux transferts en masse, une vente n'a pas
    de sens en succès partiel — on ne peut pas facturer "la moitié" d'un
    panier au client).
    """

    template_name = "dashboard/pages/admin/sales/pos/commande_form.html"

    @staticmethod
    def _agence_fixe(user) -> Optional[Any]:
        """L'agence imposée par le compte connecté (Caissier/Responsable), ou None si
        l'utilisateur (un Admin) doit la choisir explicitement dans le formulaire."""
        return user.agence if user.agence_id else None

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context.setdefault("form", CommandeForm(user=user))
        agence_fixe = self._agence_fixe(user)
        context["agence_fixe"] = agence_fixe
        context["agence_selectionnable"] = agence_fixe is None
        context["categories"] = get_categories_actives()
        if agence_fixe is None:
            context["a_une_agence_disponible"] = get_agences_autorisees(user).exists()
        else:
            context["a_une_agence_disponible"] = agence_fixe.actif
        return context

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any):
        user = request.user
        form = CommandeForm(request.POST, user=user)
        agence_fixe = self._agence_fixe(user)

        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))

        agence = agence_fixe if agence_fixe is not None else form.cleaned_data.get("agence")
        if agence is None or not agence.actif:
            messages.error(
                request,
                _("Sélectionnez une agence active pour enregistrer cette vente."),
            )
            return self.render_to_response(self.get_context_data(form=form))

        try:
            entries = json.loads(request.POST.get("entries_json") or "[]")
        except (TypeError, ValueError):
            entries = []

        if not isinstance(entries, list) or not entries:
            messages.warning(request, _("Ajoutez au moins un produit au panier avant d'encaisser."))
            return self.render_to_response(self.get_context_data(form=form))

        # Un même produit ajouté deux fois au panier : on additionne les
        # quantités plutôt que de créer deux lignes pour le même produit.
        quantites_par_produit: Dict[str, int] = {}
        for entry in entries:
            produit_id = str(entry.get("produit_id") or "")
            quantite = _to_int(entry.get("quantite"))
            if not produit_id or quantite is None or quantite <= 0:
                messages.error(request, _("Le panier contient une ligne invalide ; vente annulée."))
                return self.render_to_response(self.get_context_data(form=form))
            quantites_par_produit[produit_id] = quantites_par_produit.get(produit_id, 0) + quantite

        telephone = form.cleaned_data["client_telephone"]
        nom = form.cleaned_data["client_nom"]
        remise = form.cleaned_data.get("remise") or Decimal("0")
        taxe = form.cleaned_data.get("taxe") or Decimal("0")

        try:
            with transaction.atomic():
                client = None
                if telephone:
                    client, _created = Client.objects.get_or_create(
                        telephone=telephone, defaults={"nom": nom or telephone}
                    )

                lignes: List[LigneCommande] = []
                sous_total_general = Decimal("0")

                for produit_id, quantite in quantites_par_produit.items():
                    stock = ProduitAgence.objects.select_for_update().select_related("produit").get(
                        produit_id=produit_id, agence=agence, actif=True
                    )
                    if stock.stock_quantite < quantite:
                        raise _StockInsuffisant(stock.produit.nom, stock.stock_quantite)

                    stock.stock_quantite -= quantite
                    stock.save(update_fields=["stock_quantite", "updated_at"])

                    sous_total = stock.prix_vente * quantite
                    sous_total_general += sous_total
                    lignes.append(
                        LigneCommande(
                            produit=stock.produit,
                            quantite=quantite,
                            prix_unitaire=stock.prix_vente,
                            sous_total=sous_total,
                        )
                    )

                total = sous_total_general - remise + taxe
                if total < 0:
                    raise _RemiseExcessive

                commande = Commande.objects.create(
                    agence=agence,
                    caissier=request.user,
                    client=client,
                    remise=remise,
                    taxe=taxe,
                    total=total,
                    mode_paiement=form.cleaned_data["mode_paiement"],
                    statut=CommandeStatut.TERMINEE,
                )
                for ligne in lignes:
                    ligne.commande = commande
                LigneCommande.objects.bulk_create(lignes)
        except ProduitAgence.DoesNotExist:
            messages.error(
                request,
                _("Un des produits sélectionnés n'est plus disponible dans votre agence ; vente annulée."),
            )
            return self.render_to_response(self.get_context_data(form=form))
        except _StockInsuffisant as exc:
            messages.error(
                request,
                _("Stock insuffisant pour « %(nom)s » (disponible : %(disponible)d) ; vente annulée.")
                % {"nom": exc.nom, "disponible": exc.disponible},
            )
            return self.render_to_response(self.get_context_data(form=form))
        except _RemiseExcessive:
            messages.error(request, _("La remise dépasse le montant total de la vente ; vente annulée."))
            return self.render_to_response(self.get_context_data(form=form))

        messages.success(
            request,
            _("Vente enregistrée : %(n)d article(s) pour un total de %(total)s.")
            % {"n": len(lignes), "total": total},
        )
        return redirect("sales:commande_detail", pk=commande.pk)


class CommandeListView(LoginRequiredMixin, ListView):
    """Historique des ventes, paginé (EF-7.5, EF-9.2 à EF-9.4).

    ``select_related`` sur agence/caissier/client : évite une requête par
    ligne affichée. Le filtre agence n'est proposé que si l'utilisateur
    voit plusieurs agences (en pratique : un Admin) — pour un Responsable
    ou un Caissier, le queryset est déjà borné à une seule agence/à
    lui-même, un filtre serait redondant.
    """

    model = Commande
    template_name = "dashboard/pages/admin/sales/pos/commande_list.html"
    context_object_name = "commandes"
    paginate_by = 20

    def get_queryset(self) -> QuerySet[Commande]:
        qs = (
            get_commandes_visibles(self.request.user)
            .select_related("agence", "caissier", "client")
            .order_by("-date")
        )

        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(client__nom__icontains=q) | Q(client__telephone__icontains=q) | Q(id__icontains=q)
            )

        statut = self.request.GET.get("statut", "").strip()
        if statut:
            qs = qs.filter(statut=statut)

        agence_id = self.request.GET.get("agence", "").strip()
        if agence_id:
            qs = qs.filter(agence_id=agence_id)

        return qs

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["q"] = self.request.GET.get("q", "")
        context["statut"] = self.request.GET.get("statut", "")
        context["agence_id"] = self.request.GET.get("agence", "")
        context["statut_choices"] = CommandeStatut.choices
        agences_visibles = get_agences_visibles(self.request.user).order_by("nom")
        context["agences_visibles"] = agences_visibles if agences_visibles.count() > 1 else None
        return context


class CommandeDetailView(LoginRequiredMixin, DetailView):
    """Détail d'une vente : lignes, montants, et actions d'annulation/remboursement (EF-8).

    ``get_queryset`` repart de ``get_commandes_visibles`` : un Caissier qui
    tente d'ouvrir la vente d'un collègue via son URL directe reçoit un 404
    propre plutôt qu'une fuite d'information (même logique de revalidation
    serveur que sur les autres écrans du projet).
    """

    model = Commande
    template_name = "dashboard/pages/admin/sales/pos/commande_detail.html"
    context_object_name = "commande"

    def get_queryset(self) -> QuerySet[Commande]:
        return (
            get_commandes_visibles(self.request.user)
            .select_related("agence", "caissier", "client")
            .prefetch_related("lignes__produit")
        )

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["peut_gerer"] = getattr(self.request.user, "is_admin", False) or getattr(
            self.request.user, "is_responsable_agence", False
        )
        return context


class CommandeStatutUpdateView(LoginRequiredMixin, CommandeGestionAccessMixin, View):
    """Annuler ou rembourser une vente terminée (EF-7.5) : recrédite le stock vendu.

    C'est le "Update" du CRUD demandé : on ne modifie jamais les lignes
    d'une vente déjà enregistrée (ce serait falsifier une pièce
    comptable) — seul son statut change, avec pour effet de bord de
    recréditer le stock de chaque produit vendu dans l'agence de la vente.
    Si l'agence n'a entre-temps plus de fiche stock pour ce produit (cas
    rare), on lui en recrée une plutôt que d'échouer silencieusement.
    """

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any):
        commande = get_object_or_404(
            get_commandes_visibles(request.user).select_related("agence"), pk=kwargs["pk"]
        )

        nouveau_statut = request.POST.get("statut")
        if nouveau_statut not in {CommandeStatut.ANNULEE, CommandeStatut.REMBOURSEE}:
            messages.error(request, _("Statut demandé invalide."))
            return redirect("sales:commande_detail", pk=commande.pk)

        if commande.statut != CommandeStatut.TERMINEE:
            messages.error(request, _("Seule une vente terminée peut être annulée ou remboursée."))
            return redirect("sales:commande_detail", pk=commande.pk)

        with transaction.atomic():
            for ligne in commande.lignes.select_related("produit").all():
                stock, _created = ProduitAgence.objects.select_for_update().get_or_create(
                    produit=ligne.produit,
                    agence=commande.agence,
                    defaults={"prix_vente": ligne.prix_unitaire, "stock_quantite": 0},
                )
                stock.stock_quantite += ligne.quantite
                stock.save(update_fields=["stock_quantite", "updated_at"])

            commande.statut = nouveau_statut
            commande.save(update_fields=["statut", "updated_at"])

        libelle = "annulée" if nouveau_statut == CommandeStatut.ANNULEE else "remboursée"
        messages.success(request, _("Vente %(libelle)s ; le stock vendu a été recrédité.") % {"libelle": libelle})
        return redirect("sales:commande_detail", pk=commande.pk)