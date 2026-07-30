"""Catalogue produit et stock par agence (EF-2 à EF-5)."""
from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from general.enums import TransfertStatut
from general.models import Agence, BaseModel
from general.utils import generate_unique_slug


class Categorie(BaseModel):
    """Catégorie de produits, avec sous-catégories optionnelles (EF-2)."""

    nom = models.CharField(
        max_length=150,
        help_text="Nom de la catégorie.",
    )
    slug = models.SlugField(
        max_length=170,
        unique=True,
        blank=True,
        help_text=(
            "Identifiant lisible utilisé dans les URLs, généré automatiquement à "
            "partir du nom si laissé vide."
        ),
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="sous_categories",
        null=True,
        blank=True,
        help_text="Catégorie parente, pour créer une hiérarchie imbriquée (EF-2.2).",
    )
    image = models.ImageField(
        upload_to="categories/",
        blank=True,
        null=True,
        help_text="Image illustrant la catégorie.",
    )
    actif = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Une catégorie désactivée n'apparaît plus dans le catalogue.",
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"
        indexes = [
            models.Index(fields=["parent", "actif"]),
        ]

    def __str__(self) -> str:
        return self.nom

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = generate_unique_slug(self, "nom")
        super().save(*args, **kwargs)


class Produit(BaseModel):
    """Produit du catalogue global. Prix et stock vivent sur ProduitAgence (EF-3)."""

    nom = models.CharField(
        max_length=200,
        db_index=True,
        help_text="Nom commercial du produit.",
    )
    sku = models.CharField(
        max_length=64,
        unique=True,
        help_text="SKU / code-barres unique du produit (EF-3.1).",
    )
    categorie = models.ForeignKey(
        Categorie,
        on_delete=models.PROTECT,
        related_name="produits",
        help_text="Catégorie à laquelle appartient ce produit.",
    )
    prix_achat = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text=(
            "Prix d'achat / coût de revient du produit. Commun à toutes les "
            "agences (contrairement au prix de vente, fixé par agence)."
        ),
    )
    prix_vente_defaut = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text=(
            "Prix de vente par défaut, utilisé pour pré-remplir le prix d'une "
            "nouvelle fiche ProduitAgence. Chaque agence peut ensuite fixer son "
            "propre prix de vente (EF-4.2)."
        ),
    )
    unite = models.CharField(
        max_length=30,
        default="unité",
        help_text="Unité de vente (pièce, kg, litre...).",
    )
    image = models.ImageField(
        upload_to="produits/",
        blank=True,
        null=True,
        help_text="Photo du produit.",
    )
    description = models.TextField(
        blank=True,
        help_text="Description commerciale du produit.",
    )
    actif = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Un produit désactivé ne peut plus être proposé par une agence.",
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Produit"
        verbose_name_plural = "Produits"
        indexes = [
            models.Index(fields=["categorie", "actif"]),
            models.Index(fields=["sku"]),
        ]

    def __str__(self) -> str:
        return f"{self.nom} ({self.sku})"


class ProduitAgence(BaseModel):
    """Prix et stock d'un produit pour une agence donnée (EF-4).

    Correspond à "BranchProduct" dans les exigences fonctionnelles.
    """

    produit = models.ForeignKey(
        Produit,
        on_delete=models.CASCADE,
        related_name="prix_stocks",
        help_text="Produit concerné.",
    )
    agence = models.ForeignKey(
        Agence,
        on_delete=models.CASCADE,
        related_name="produits_agence",
        help_text="Agence concernée.",
    )
    prix_vente = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text=(
            "Prix de vente pratiqué par cette agence pour ce produit. Peut "
            "différer du prix_vente_defaut du produit (EF-4.2)."
        ),
    )
    stock_quantite = models.PositiveIntegerField(
        default=0,
        help_text="Quantité actuellement en stock dans cette agence.",
    )
    seuil_alerte = models.PositiveIntegerField(
        default=0,
        help_text="Seuil sous lequel une alerte de stock bas est déclenchée (EF-4.4).",
    )
    actif = models.BooleanField(
        default=True,
        help_text="Une fiche inactive : ce produit n'est pas proposé par cette agence (EF-4.2).",
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Prix & stock par agence"
        verbose_name_plural = "Prix & stocks par agence"
        constraints = [
            models.UniqueConstraint(fields=["produit", "agence"], name="unique_produit_par_agence"),
        ]
        indexes = [
            models.Index(fields=["agence", "actif"]),
            models.Index(fields=["stock_quantite"]),
        ]

    def __str__(self) -> str:
        return f"{self.produit} @ {self.agence}"

    @property
    def stock_bas(self) -> bool:
        """True si le stock est descendu sous (ou à) le seuil d'alerte (EF-4.4)."""
        return self.stock_quantite <= self.seuil_alerte


class TransfertStock(BaseModel):
    """Demande de transfert de stock d'une agence vers une autre (EF-5)."""

    produit = models.ForeignKey(
        Produit,
        on_delete=models.PROTECT,
        related_name="transferts",
        help_text="Produit transféré.",
    )
    agence_source = models.ForeignKey(
        Agence,
        on_delete=models.PROTECT,
        related_name="transferts_source",
        help_text="Agence d'origine du transfert.",
    )
    agence_destination = models.ForeignKey(
        Agence,
        on_delete=models.PROTECT,
        related_name="transferts_destination",
        help_text="Agence de destination du transfert.",
    )
    quantite = models.PositiveIntegerField(
        help_text="Quantité à transférer.",
    )
    statut = models.CharField(
        max_length=20,
        choices=TransfertStatut.choices,
        default=TransfertStatut.EN_ATTENTE,
        db_index=True,
        help_text="Statut courant du transfert (EF-5.2).",
    )
    demande_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="transferts_demandes",
        help_text="Utilisateur ayant initié la demande de transfert (EF-5.1).",
    )
    approuve_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="transferts_approuves",
        null=True,
        blank=True,
        help_text="Utilisateur ayant approuvé le transfert, le cas échéant (EF-5.2).",
    )
    date_transfert = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date à laquelle le transfert a été finalisé.",
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Transfert de stock"
        verbose_name_plural = "Transferts de stock"
        indexes = [
            models.Index(fields=["statut", "created_at"]),
            models.Index(fields=["agence_source", "agence_destination"]),
        ]

    def __str__(self) -> str:
        return f"{self.produit} : {self.agence_source} -> {self.agence_destination} ({self.quantite})"

    def clean(self) -> None:
        super().clean()
        if (
            self.agence_source_id
            and self.agence_destination_id
            and self.agence_source_id == self.agence_destination_id
        ):
            raise ValidationError(
                _("L'agence source et l'agence destination doivent être différentes.")
            )