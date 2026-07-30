"""Clients et ventes / point de vente (EF-6 à EF-8)."""
from __future__ import annotations

from django.conf import settings
from django.db import models

from general.enums import CommandeStatut, ModePaiement, Role
from general.models import Agence, BaseModel
from products.models import Produit


class Client(BaseModel):
    """Client de la boutique (EF-6). Le téléphone sert de clé naturelle."""

    nom = models.CharField(
        max_length=150,
        help_text="Nom complet du client.",
    )
    telephone = models.CharField(
        max_length=30,
        unique=True,
        db_index=True,
        help_text=(
            "Numéro de téléphone : clé naturelle utilisée pour éviter les doublons "
            "lorsqu'un même client est saisi avec une orthographe de nom différente (EF-6.4)."
        ),
    )
    email = models.EmailField(
        blank=True,
        help_text="Email du client (optionnel).",
    )
    adresse = models.CharField(
        max_length=255,
        blank=True,
        help_text="Adresse du client (optionnelle).",
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Client"
        verbose_name_plural = "Clients"
        indexes = [
            models.Index(fields=["nom"]),
        ]

    def __str__(self) -> str:
        return f"{self.nom} ({self.telephone})"


class Commande(BaseModel):
    """Une vente / commande passée au point de vente (EF-7)."""

    agence = models.ForeignKey(
        Agence,
        on_delete=models.PROTECT,
        related_name="commandes",
        help_text="Agence dans laquelle la vente a été réalisée.",
    )
    caissier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="commandes_realisees",
        limit_choices_to={"role": Role.CAISSIER},
        help_text="Caissier ayant réalisé la vente.",
    )
    client = models.ForeignKey(
        Client,
        on_delete=models.SET_NULL,
        related_name="commandes",
        null=True,
        blank=True,
        help_text="Client de la vente. Facultatif : une vente 'client de passage' est valide (EF-6.1).",
    )
    remise = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Montant de la remise appliquée à la commande (EF-7.2).",
    )
    taxe = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Montant de la taxe appliquée à la commande (EF-7.2).",
    )
    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Total de la commande, recalculé par signal à partir des lignes (EF-13.4).",
    )
    mode_paiement = models.CharField(
        max_length=20,
        choices=ModePaiement.choices,
        help_text="Mode de paiement utilisé (EF-7.2).",
    )
    statut = models.CharField(
        max_length=20,
        choices=CommandeStatut.choices,
        default=CommandeStatut.EN_ATTENTE,
        db_index=True,
        help_text="Cycle de vie de la commande (EF-7.5).",
    )
    date = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Date et heure de la vente.",
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Commande"
        verbose_name_plural = "Commandes"
        indexes = [
            models.Index(fields=["agence", "statut", "date"]),
            models.Index(fields=["caissier", "date"]),
        ]

    def __str__(self) -> str:
        return f"Commande {self.id} - {self.agence}"


class LigneCommande(BaseModel):
    """Une ligne d'une commande : produit, quantité, prix figé (EF-7.4)."""

    commande = models.ForeignKey(
        Commande,
        on_delete=models.CASCADE,
        related_name="lignes",
        help_text="Commande à laquelle appartient cette ligne.",
    )
    produit = models.ForeignKey(
        Produit,
        on_delete=models.PROTECT,
        related_name="lignes_commande",
        help_text="Produit vendu.",
    )
    quantite = models.PositiveIntegerField(
        help_text="Quantité vendue.",
    )
    prix_unitaire = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text=(
            "Prix unitaire figé au moment de la vente (copié depuis ProduitAgence), "
            "pour ne pas modifier l'historique si le prix change ensuite (EF-7.4)."
        ),
    )
    sous_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="quantité x prix_unitaire, calculé par signal (EF-13.4).",
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Ligne de commande"
        verbose_name_plural = "Lignes de commande"
        indexes = [
            models.Index(fields=["commande"]),
            models.Index(fields=["produit"]),
        ]

    def __str__(self) -> str:
        return f"{self.quantite} x {self.produit}"


class Recu(BaseModel):
    """Reçu généré automatiquement pour une commande terminée (EF-8)."""

    commande = models.OneToOneField(
        Commande,
        on_delete=models.CASCADE,
        related_name="recu",
        help_text="Commande terminée associée à ce reçu (relation un-à-un, EF-8.1).",
    )
    numero_recu = models.CharField(
        max_length=40,
        unique=True,
        db_index=True,
        help_text="Numéro unique du reçu, utilisé pour la recherche (EF-8.3).",
    )
    fichier_pdf = models.FileField(
        upload_to="recus/",
        blank=True,
        null=True,
        help_text="Version PDF téléchargeable du reçu (EF-8.2).",
    )
    date_generation = models.DateTimeField(
        auto_now_add=True,
        help_text="Date et heure de génération du reçu.",
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Reçu"
        verbose_name_plural = "Reçus"

    def __str__(self) -> str:
        return self.numero_recu