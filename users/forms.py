"""Formulaires d'authentification et de création de compte (EF-9)."""
from __future__ import annotations

from typing import Any, Optional

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.utils.translation import gettext_lazy as _

from general.enums import Role
from users.models import Utilisateur

TAILWIND_INPUT_CLASSES = (
    "block w-full rounded-lg border border-gray-300 bg-white py-2.5 px-3 text-sm "
    "text-gray-900 placeholder-gray-400 shadow-sm transition focus:border-primary-600 "
    "focus:outline-none focus:ring-2 focus:ring-primary-600/30"
)


class UtilisateurCreationForm(UserCreationForm):
    """Création d'un compte employé par un Admin ou un Responsable d'agence.

    Pas d'inscription publique : ce formulaire est rendu derrière
    login_required + une vérification de permission (voir
    UtilisateurCreateView). Un Responsable ne peut créer que des Caissiers,
    rattachés à sa propre agence (EF-9.3) ; ces deux champs sont alors
    verrouillés côté formulaire ET revalidés côté vue.
    """

    class Meta(UserCreationForm.Meta):
        model = Utilisateur
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "telephone",
            "role",
            "agence",
        )

    def __init__(self, *args: Any, created_by: Optional[Utilisateur] = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.created_by = created_by

        for field in self.fields.values():
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{existing} {TAILWIND_INPUT_CLASSES}".strip()

        if created_by is not None and created_by.is_responsable_agence:
            # Un Responsable ne peut créer que des Caissiers, dans sa propre agence.
            self.fields["role"].choices = [(Role.CAISSIER.value, Role.CAISSIER.label)]
            self.fields["role"].initial = Role.CAISSIER
            self.fields["role"].disabled = True
            self.fields["agence"].initial = created_by.agence_id
            self.fields["agence"].disabled = True
            self.fields["agence"].widget = forms.HiddenInput()

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean()

        # Un Responsable ne peut pas contourner les champs verrouillés en
        # modifiant le HTML envoyé : on réaffirme la règle ici, côté serveur.
        if self.created_by is not None and self.created_by.is_responsable_agence:
            cleaned["role"] = Role.CAISSIER
            cleaned["agence"] = self.created_by.agence

        role = cleaned.get("role")
        agence = cleaned.get("agence")
        if role and role != Role.ADMIN and agence is None:
            self.add_error("agence", _("Une agence est obligatoire pour ce rôle (EF-9.3, EF-9.4)."))

        return cleaned