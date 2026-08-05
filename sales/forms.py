"""Formulaires du module ventes / point de vente (EF-6, EF-7)."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from django import forms

from general.enums import ModePaiement
from products.services import get_agences_autorisees
from sales.models import Client

TAILWIND_INPUT_CLASSES = (
    "block w-full rounded-lg border border-gray-300 bg-white py-2.5 px-3 text-sm "
    "text-gray-900 placeholder-gray-400 shadow-sm transition focus:border-primary-600 "
    "focus:outline-none focus:ring-2 focus:ring-primary-600/30"
)


class _TailwindFormMixin:
    """Applique les classes Tailwind à tous les widgets (voir products/forms.py)."""

    def _apply_tailwind(self) -> None:
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                continue
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{existing} {TAILWIND_INPUT_CLASSES}".strip()


class CommandeForm(_TailwindFormMixin, forms.Form):
    """En-tête d'une vente au point de vente (EF-7.2).

    Le panier de produits (potentiellement plusieurs articles à la fois)
    n'est PAS un champ de ce formulaire : comme pour les transferts de
    stock, il est saisi via une interface "panier" en JS et soumis dans un
    champ caché ``entries_json`` (voir CommandeCreateView.post).

    N'importe quel rôle peut désormais encaisser (Admin, Responsable
    d'agence, Caissier) — la vente n'est plus réservée aux seuls Caissiers.
    Un utilisateur rattaché à une agence fixe (Caissier ou Responsable) n'a
    pas de champ agence à remplir : la vue impose sa propre agence,
    inutile de le lui laisser choisir. Un Admin (sans agence de
    rattachement) doit en revanche choisir explicitement l'agence de la
    vente parmi celles auxquelles il a accès (``get_agences_autorisees``,
    revalidé côté serveur comme pour les transferts de stock).

    Le client est optionnel ("vente à un client de passage", EF-6.1). S'il
    est identifié par téléphone et qu'aucun client n'existe déjà avec ce
    numéro, le nom devient obligatoire pour créer sa fiche à la volée
    (EF-6.4 : le téléphone sert de clé naturelle pour éviter les doublons
    quand un même client est ressaisi avec une orthographe différente).
    """

    client_telephone = forms.CharField(
        label="Téléphone du client",
        required=False,
        help_text="Laissez vide pour une vente sans client identifié.",
    )
    client_nom = forms.CharField(
        label="Nom du client",
        required=False,
        help_text="Requis uniquement si ce numéro ne correspond à aucun client existant.",
    )
    remise = forms.DecimalField(
        label="Remise",
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0"),
        required=False,
        initial=Decimal("0"),
    )
    taxe = forms.DecimalField(
        label="Taxe",
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0"),
        required=False,
        initial=Decimal("0"),
    )
    mode_paiement = forms.ChoiceField(label="Mode de paiement", choices=ModePaiement.choices)

    def __init__(self, *args: Any, user: Any = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if user is not None and not getattr(user, "agence_id", None):
            self.fields["agence"] = forms.ModelChoiceField(
                queryset=get_agences_autorisees(user),
                label="Agence de vente",
                help_text="Agence dans laquelle cette vente est enregistrée.",
            )
        self._apply_tailwind()

    def clean(self) -> dict:
        cleaned = super().clean()
        telephone = (cleaned.get("client_telephone") or "").strip()
        nom = (cleaned.get("client_nom") or "").strip()

        if telephone and not nom and not Client.objects.filter(telephone=telephone).exists():
            self.add_error(
                "client_nom",
                "Indiquez le nom du client pour créer sa fiche "
                "(aucun client existant avec ce numéro).",
            )

        cleaned["client_telephone"] = telephone
        cleaned["client_nom"] = nom
        return cleaned