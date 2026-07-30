"""Modèles partagés par toute l'application : BaseModel, Agence, ParametresEntreprise.

BaseModel est la classe abstraite dont hérite CHAQUE modèle du domaine
(EF-13.6). Agence et ParametresEntreprise vivent ici plutôt que dans
users/products/sales car elles sont référencées par les quatre apps —
les y placer éviterait des imports circulaires.
"""
from __future__ import annotations

import uuid
from typing import Optional

from django.core.cache import cache
from django.db import models

from general.utils import generate_unique_slug


class BaseModel(models.Model):
    """Classe abstraite commune à tous les modèles du domaine (EF-13.6).

    Fournit ``id`` (UUID), ``created_at`` et ``updated_at``. Chaque modèle
    métier doit en hériter au lieu de redéfinir ces champs.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Identifiant unique (UUID) de l'enregistrement.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Date et heure de création de l'enregistrement.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Date et heure de la dernière modification.",
    )

    class Meta:
        abstract = True
        ordering = ["-created_at"]


class Agence(BaseModel):
    """Une agence / point de vente (EF-1.1)."""

    nom = models.CharField(
        max_length=150,
        help_text="Nom commercial de l'agence.",
    )
    slug = models.SlugField(
        max_length=170,
        unique=True,
        blank=True,
        help_text=(
            "Identifiant unique de l'agence utilisé dans les URLs (ex: /agences/"
            "<slug>/) à la place de l'UUID, notamment pour les liens visités par "
            "un Responsable d'agence ou un Caissier après connexion. Généré "
            "automatiquement à partir du nom si laissé vide."
        ),
    )
    adresse = models.CharField(
        max_length=255,
        blank=True,
        help_text="Adresse physique de l'agence.",
    )
    telephone = models.CharField(
        max_length=30,
        blank=True,
        help_text="Numéro de téléphone de contact de l'agence.",
    )
    actif = models.BooleanField(
        default=True,
        db_index=True,
        help_text=(
            "Une agence désactivée est exclue des écrans de vente/POS mais "
            "reste visible dans l'historique et les rapports (EF-1.3)."
        ),
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Agence"
        verbose_name_plural = "Agences"
        indexes = [
            models.Index(fields=["nom"]),
            models.Index(fields=["actif", "nom"]),
        ]

    def __str__(self) -> str:
        return self.nom

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = generate_unique_slug(self, "nom")
        super().save(*args, **kwargs)


class ParametresEntreprise(BaseModel):
    """Paramètres globaux de l'entreprise, singleton unique (EF-10.1)."""

    SINGLETON_ID = uuid.UUID(int=1)

    nom = models.CharField(
        max_length=150,
        help_text="Raison sociale affichée sur les reçus et l'en-tête de l'application.",
    )
    logo = models.ImageField(
        upload_to="entreprise/",
        blank=True,
        null=True,
        help_text="Logo affiché sur les reçus et l'en-tête de l'application.",
    )
    slogan = models.CharField(
        max_length=255,
        blank=True,
        help_text="Slogan de l'entreprise.",
    )
    adresse = models.CharField(
        max_length=255,
        blank=True,
        help_text="Adresse du siège social.",
    )
    telephone = models.CharField(
        max_length=30,
        blank=True,
        help_text="Téléphone de contact principal.",
    )
    email = models.EmailField(
        blank=True,
        help_text="Email de contact principal.",
    )
    site_web = models.URLField(
        blank=True,
        help_text="Site web de l'entreprise.",
    )
    tax_id = models.CharField(
        max_length=50,
        blank=True,
        help_text="Numéro fiscal / identifiant contribuable, affiché sur les reçus.",
    )
    devise = models.CharField(
        max_length=10,
        default="FCFA",
        help_text="Symbole monétaire utilisé dans toute l'application.",
    )
    note_pied_page = models.TextField(
        blank=True,
        help_text="Note affichée en bas des reçus (conditions, remerciements...).",
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Paramètres de l'entreprise"
        verbose_name_plural = "Paramètres de l'entreprise"

    def __str__(self) -> str:
        return self.nom or "Paramètres de l'entreprise"

    def save(self, *args, **kwargs) -> None:
        """Force le singleton (pk fixe) et invalide le cache (EF-10.3)."""
        self.pk = self.SINGLETON_ID
        super().save(*args, **kwargs)
        cache.delete("parametres_entreprise")

    def delete(self, *args, **kwargs) -> None:
        # EF-11.3: pas de suppression du singleton depuis l'admin.
        raise PermissionError("Les paramètres de l'entreprise ne peuvent pas être supprimés.")

    @classmethod
    def load(cls) -> "ParametresEntreprise":
        """Récupère (ou crée) l'unique instance, avec mise en cache (EF-10.2, EF-13.2)."""
        obj: Optional["ParametresEntreprise"] = cache.get("parametres_entreprise")
        if obj is None:
            obj, _created = cls.objects.get_or_create(
                pk=cls.SINGLETON_ID, defaults={"nom": "Ma Boutique"}
            )
            cache.set("parametres_entreprise", obj, None)
        return obj