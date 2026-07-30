"""Formulaires de l'app general."""
from __future__ import annotations

from typing import Any

from django import forms

from general.models import ParametresEntreprise

TAILWIND_INPUT_CLASSES = (
    "block w-full rounded-lg border border-gray-300 bg-white py-2.5 px-3 text-sm "
    "text-gray-900 placeholder-gray-400 shadow-sm transition focus:border-primary-600 "
    "focus:outline-none focus:ring-2 focus:ring-primary-600/30"
)


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