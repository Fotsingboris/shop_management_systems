"""Formulaires du catalogue produit (EF-2, EF-3, EF-4)."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from django import forms

from products.models import Categorie, ImportCategories, ImportProduits, Produit

TAILWIND_INPUT_CLASSES = (
    "block w-full rounded-lg border border-gray-300 bg-white py-2.5 px-3 text-sm "
    "text-gray-900 placeholder-gray-400 shadow-sm transition focus:border-primary-600 "
    "focus:outline-none focus:ring-2 focus:ring-primary-600/30"
)


class _TailwindFormMixin:
    """Applique les classes Tailwind à tous les widgets, sauf case à cocher/fichier."""

    def _apply_tailwind(self) -> None:
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                continue
            if isinstance(field.widget, forms.ClearableFileInput):
                field.widget.attrs["class"] = "block w-full text-sm text-gray-600"
                continue
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{existing} {TAILWIND_INPUT_CLASSES}".strip()


class CategorieForm(_TailwindFormMixin, forms.ModelForm):
    """Création/édition d'une catégorie (EF-2.1)."""

    class Meta:
        model = Categorie
        fields = ["nom", "parent", "image", "actif"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        queryset = Categorie.objects.filter(actif=True).order_by("nom")
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        self.fields["parent"].queryset = queryset
        self.fields["parent"].required = False
        self._apply_tailwind()


class CategorieImportForm(_TailwindFormMixin, forms.ModelForm):
    """Upload du fichier Excel à importer (EF-2.3)."""

    class Meta:
        model = ImportCategories
        fields = ["fichier"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._apply_tailwind()

    def clean_fichier(self):
        fichier = self.cleaned_data["fichier"]
        if not fichier.name.lower().endswith((".xlsx", ".xlsm")):
            raise forms.ValidationError("Le fichier doit être un classeur Excel (.xlsx).")
        return fichier


class StockAjustementForm(_TailwindFormMixin, forms.Form):
    """Réapprovisionnement/correction d'une fiche ProduitAgence existante (EF-4.2, EF-4.3, EF-4.4).

    Formulaire simple (pas un ModelForm) car la quantité ne se traite pas
    comme les autres champs : elle s'AJOUTE au stock actuel plutôt que de
    le remplacer, pour ne pas obliger à ressaisir le total exact à chaque
    réappro (« le stock peut être ajouté à tout moment »). Le prix de
    vente et le seuil d'alerte, eux, sont bien remplacés directement.
    """

    quantite_a_ajouter = forms.IntegerField(
        label="Quantité à ajouter",
        initial=0,
        help_text="Positif pour un réapprovisionnement, négatif pour corriger une erreur de comptage.",
    )
    prix_vente = forms.DecimalField(
        label="Prix de vente",
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )
    seuil_alerte = forms.IntegerField(
        label="Seuil d'alerte",
        min_value=0,
        help_text="Stock à partir duquel cette fiche est signalée « Stock bas ».",
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._apply_tailwind()


class ProduitForm(_TailwindFormMixin, forms.ModelForm):
    """Création/édition d'un produit du catalogue (EF-3.1).

    Ne couvre volontairement que les champs communs à toutes les agences
    (nom, SKU, catégorie, prix d'achat, prix de vente par défaut...). Le
    prix de vente réel et le stock, qui varient par agence, se gèrent
    depuis « Stock & prix » (ProduitAgence) — pas ici (EF-4).
    """

    class Meta:
        model = Produit
        fields = [
            "nom",
            "sku",
            "categorie",
            "prix_achat",
            "prix_vente_defaut",
            "unite",
            "image",
            "description",
            "actif",
        ]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Vrai queryset (pas la liste mise en cache de products.services) :
        # ModelChoiceField doit pouvoir interroger la base pour valider la
        # valeur soumise.
        self.fields["categorie"].queryset = Categorie.objects.filter(actif=True).order_by("nom")
        self._apply_tailwind()


class ProduitImportForm(_TailwindFormMixin, forms.ModelForm):
    """Upload du fichier Excel de produits à importer (EF-3.1)."""

    class Meta:
        model = ImportProduits
        fields = ["fichier"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._apply_tailwind()

    def clean_fichier(self):
        fichier = self.cleaned_data["fichier"]
        if not fichier.name.lower().endswith((".xlsx", ".xlsm")):
            raise forms.ValidationError("Le fichier doit être un classeur Excel (.xlsx).")
        return fichier