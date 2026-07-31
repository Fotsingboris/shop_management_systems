"""Formulaires de l'app general."""
from __future__ import annotations

from typing import Any

from django import forms

from general.models import Agence, ParametresEntreprise

TAILWIND_INPUT_CLASSES = (
    "block w-full rounded-lg border border-gray-300 bg-white py-2.5 px-3 text-sm "
    "text-gray-900 placeholder-gray-400 shadow-sm transition focus:border-primary-600 "
    "focus:outline-none focus:ring-2 focus:ring-primary-600/30"
)


def _apply_tailwind(form: forms.ModelForm) -> None:
    """Applique les classes Tailwind à tous les widgets, sauf case à cocher/fichier.

    Factorisé ici (au lieu de dupliquer la boucle dans chaque __init__,
    comme le faisait ParametresEntrepriseForm) pour être réutilisé par
    AgenceForm.
    """
    for field in form.fields.values():
        if isinstance(field.widget, forms.CheckboxInput):
            continue
        if isinstance(field.widget, forms.ClearableFileInput):
            field.widget.attrs["class"] = "block w-full text-sm text-gray-600"
            continue
        existing = field.widget.attrs.get("class", "")
        field.widget.attrs["class"] = f"{existing} {TAILWIND_INPUT_CLASSES}".strip()


class ParametresEntrepriseForm(forms.ModelForm):
    """Édition du singleton ParametresEntreprise (EF-10.1)."""

    class Meta:
        model = ParametresEntreprise
        fields = [
            "nom",
            "logo",
            "slogan",
            "adresse",
            "telephone",
            "email",
            "site_web",
            "tax_id",
            "devise",
            "note_pied_page",
        ]
        widgets = {
            "note_pied_page": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.ClearableFileInput):
                field.widget.attrs["class"] = "block w-full text-sm text-gray-600"
                continue
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{existing} {TAILWIND_INPUT_CLASSES}".strip()


class AgenceForm(forms.ModelForm):
    """Création/édition d'une agence (EF-1.1).

    Le slug n'est volontairement pas un champ du formulaire : il est
    généré automatiquement à partir du nom par Agence.save() si vide, et
    reste stable une fois posé (utilisé dans les URLs de tableau de bord
    des Responsables/Caissiers de cette agence).
    """

    class Meta:
        model = Agence
        fields = ["nom", "adresse", "telephone", "actif"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        _apply_tailwind(self)