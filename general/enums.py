"""Enums partagés par tout le projet.

Centraliser les choix ici évite la duplication et les imports circulaires
entre applications (users, products, sales, general). Toute application
peut importer ce module sans risque, car il ne dépend d'aucun modèle.
"""
from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _


class Role(models.TextChoices):
    """Rôles disponibles pour un Utilisateur (EF-9.1)."""

    ADMIN = "ADMIN", _("Admin")
    RESPONSABLE_AGENCE = "RESPONSABLE_AGENCE", _("Responsable d'agence")
    CAISSIER = "CAISSIER", _("Caissier")


class TransfertStatut(models.TextChoices):
    """Cycle de vie d'un TransfertStock (EF-5.2)."""

    EN_ATTENTE = "EN_ATTENTE", _("En attente")
    APPROUVE = "APPROUVE", _("Approuvé")
    TERMINE = "TERMINE", _("Terminé")
    ANNULE = "ANNULE", _("Annulé")


class CommandeStatut(models.TextChoices):
    """Cycle de vie d'une Commande (EF-7.5)."""

    EN_ATTENTE = "EN_ATTENTE", _("En attente")
    TERMINEE = "TERMINEE", _("Terminée")
    REMBOURSEE = "REMBOURSEE", _("Remboursée")
    ANNULEE = "ANNULEE", _("Annulée")


class ModePaiement(models.TextChoices):
    """Modes de paiement acceptés au point de vente (EF-7.2)."""

    ESPECES = "ESPECES", _("Espèces")
    CARTE = "CARTE", _("Carte bancaire")
    MOBILE_MONEY = "MOBILE_MONEY", _("Mobile money")
    AUTRE = "AUTRE", _("Autre")