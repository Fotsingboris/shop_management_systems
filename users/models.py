"""Utilisateur personnalisé et sous-types par rôle (EF-9).

Utilisateur est la seule table concrète (AUTH_USER_MODEL). Admin,
ResponsableAgence et Caissier sont des *proxy models* : même table, même
champs, mais des managers et un comportement propres à chaque rôle. Ce
choix respecte le "héritage" décrit dans le diagramme de classes sans
éclater les utilisateurs sur plusieurs tables pour un simple champ role.
"""
from __future__ import annotations

from typing import Optional

from django.contrib.auth.models import AbstractUser, UserManager
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _

from general.enums import Role
from general.models import Agence, BaseModel


class RoleManager(UserManager):
    """Manager de base : restreint le queryset à un rôle donné.

    Hérite de UserManager (et non de models.Manager) pour conserver
    create_user()/create_superuser(), utilisés par `createsuperuser`.
    """

    role: Optional[str] = None

    def get_queryset(self) -> QuerySet["Utilisateur"]:
        qs = super().get_queryset()
        if self.role is not None:
            qs = qs.filter(role=self.role)
        return qs


class AdminManager(RoleManager):
    role = Role.ADMIN


class ResponsableAgenceManager(RoleManager):
    role = Role.RESPONSABLE_AGENCE


class CaissierManager(RoleManager):
    role = Role.CAISSIER


class Utilisateur(AbstractUser, BaseModel):
    """Profil commun à tous les utilisateurs du système (EF-9.1).

    Hérite de AbstractUser (authentification Django : username, email,
    password, permissions...) et de BaseModel (id UUID, created_at,
    updated_at).
    """

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        db_index=True,
        help_text="Rôle de l'utilisateur : détermine son périmètre d'accès (EF-9.2 à EF-9.4).",
    )
    agence = models.ForeignKey(
        Agence,
        on_delete=models.PROTECT,
        related_name="utilisateurs",
        null=True,
        blank=True,
        help_text=(
            "Agence de rattachement. Obligatoire pour un Responsable d'agence ou un "
            "Caissier ; laisser vide pour un Admin (accès à toutes les agences)."
        ),
    )
    telephone = models.CharField(
        max_length=30,
        blank=True,
        help_text="Numéro de téléphone professionnel de l'utilisateur.",
    )

    # Manager par défaut (toutes les instances, tous rôles confondus) — celui
    # utilisé par `createsuperuser` et par Django pour l'authentification.
    objects = UserManager()

    class Meta(BaseModel.Meta):
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"
        indexes = [
            models.Index(fields=["role"]),
            models.Index(fields=["agence", "role"]),
        ]

    def __str__(self) -> str:
        return self.get_full_name() or self.username

    def clean(self) -> None:
        super().clean()
        if self.role != Role.ADMIN and self.agence_id is None:
            raise ValidationError(
                {"agence": _("Une agence est obligatoire pour ce rôle (EF-9.3, EF-9.4).")}
            )

    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN

    @property
    def is_responsable_agence(self) -> bool:
        return self.role == Role.RESPONSABLE_AGENCE

    @property
    def is_caissier(self) -> bool:
        return self.role == Role.CAISSIER


class Admin(Utilisateur):
    """Proxy : accès sans restriction à toutes les agences (EF-9.2)."""

    objects = AdminManager()

    class Meta:
        proxy = True
        verbose_name = "Admin"
        verbose_name_plural = "Admins"


class ResponsableAgence(Utilisateur):
    """Proxy : limité à son agence assignée pour prix/stock, caissiers et rapports (EF-9.3)."""

    objects = ResponsableAgenceManager()

    class Meta:
        proxy = True
        verbose_name = "Responsable d'agence"
        verbose_name_plural = "Responsables d'agence"


class Caissier(Utilisateur):
    """Proxy : limité à la création de ventes/reçus et à son historique (EF-9.4)."""

    objects = CaissierManager()

    class Meta:
        proxy = True
        verbose_name = "Caissier"
        verbose_name_plural = "Caissiers"