"""Admin Django pour les clients et les ventes (EF-11.1, EF-11.2)."""
from __future__ import annotations

from django.contrib import admin

from sales.models import Client, Commande, LigneCommande, Recu


class LigneCommandeInline(admin.TabularInline):
    """Lignes modifiables en ligne sur la fiche Commande (EF-11.2)."""

    model = LigneCommande
    extra = 0
    fields = ("produit", "quantite", "prix_unitaire", "sous_total")
    autocomplete_fields = ("produit",)


class RecuInline(admin.StackedInline):
    """Reçu associé, en relation un-à-un (EF-8.1)."""

    model = Recu
    extra = 0
    max_num = 1
    fields = ("numero_recu", "fichier_pdf", "date_generation")
    readonly_fields = ("date_generation",)


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("nom", "telephone", "email")
    search_fields = ("nom", "telephone", "email")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("nom",)


@admin.register(Commande)
class CommandeAdmin(admin.ModelAdmin):
    list_display = ("id", "agence", "caissier", "client", "total", "statut", "mode_paiement", "date")
    list_filter = ("statut", "mode_paiement", "agence")
    # "=id" : recherche exacte sur l'UUID plutôt qu'un icontains coûteux.
    search_fields = ("=id", "client__nom", "client__telephone", "caissier__username")
    autocomplete_fields = ("agence", "caissier", "client")
    # `total` reste éditable pour l'instant (pas encore recalculé par signal,
    # voir EF-13.4) ; à passer en readonly une fois ce signal implémenté.
    readonly_fields = ("date", "created_at", "updated_at")
    list_select_related = ("agence", "caissier", "client")
    date_hierarchy = "date"
    inlines = [LigneCommandeInline, RecuInline]


@admin.register(Recu)
class RecuAdmin(admin.ModelAdmin):
    """Recherche par numéro de reçu ou par ID de commande (EF-8.3)."""

    list_display = ("numero_recu", "commande", "date_generation")
    search_fields = ("numero_recu", "=commande__id")
    readonly_fields = ("date_generation",)
    list_select_related = ("commande",)