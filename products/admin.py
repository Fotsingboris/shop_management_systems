"""Admin Django pour le catalogue produit et le stock par agence (EF-11.1, EF-11.2)."""
from __future__ import annotations

from django.contrib import admin

from products.models import (
    Categorie,
    ImportCategories,
    ImportProduits,
    Produit,
    ProduitAgence,
    TransfertStock,
)


class ProduitAgenceInline(admin.TabularInline):
    """Prix/stock par agence, modifiables en ligne sur la fiche Produit (EF-11.2)."""

    model = ProduitAgence
    extra = 0
    fields = ("agence", "prix_vente", "stock_quantite", "seuil_alerte", "actif")
    autocomplete_fields = ("agence",)


@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    list_display = ("nom", "parent", "actif")
    list_filter = ("actif", "parent")
    search_fields = ("nom", "slug")
    prepopulated_fields = {"slug": ("nom",)}
    readonly_fields = ("created_at", "updated_at")
    ordering = ("nom",)


@admin.register(Produit)
class ProduitAdmin(admin.ModelAdmin):
    list_display = ("nom", "sku", "categorie", "prix_achat", "prix_vente_defaut", "actif")
    list_filter = ("actif", "categorie")
    search_fields = ("nom", "sku")
    autocomplete_fields = ("categorie",)
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("categorie",)
    inlines = [ProduitAgenceInline]
    ordering = ("nom",)


@admin.register(ProduitAgence)
class ProduitAgenceAdmin(admin.ModelAdmin):
    """Vue transverse (filtrage par agence, stock bas...) en plus de
    l'édition en ligne depuis la fiche Produit."""

    list_display = ("produit", "agence", "prix_vente", "stock_quantite", "seuil_alerte", "actif")
    list_filter = ("agence", "actif")
    search_fields = ("produit__nom", "produit__sku", "agence__nom")
    autocomplete_fields = ("produit", "agence")
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("produit", "agence")


@admin.register(TransfertStock)
class TransfertStockAdmin(admin.ModelAdmin):
    list_display = (
        "produit",
        "agence_source",
        "agence_destination",
        "quantite",
        "statut",
        "demande_par",
        "date_transfert",
    )
    list_filter = ("statut", "agence_source", "agence_destination")
    search_fields = ("produit__nom", "produit__sku")
    autocomplete_fields = ("produit", "agence_source", "agence_destination", "demande_par", "approuve_par")
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("produit", "agence_source", "agence_destination", "demande_par", "approuve_par")
    date_hierarchy = "created_at"


class _ImportAdmin(admin.ModelAdmin):
    """Base commune : ces fiches ne se créent/modifient que via l'upload
    (EF-2.3, EF-3.1), l'admin sert uniquement à consulter le résultat."""

    list_display = ("nom_fichier", "statut", "lignes_reussies", "lignes_echouees", "importe_par", "created_at")
    list_filter = ("statut",)
    readonly_fields = (
        "fichier", "statut", "total_lignes", "lignes_reussies", "lignes_echouees",
        "rapport", "importe_par", "created_at", "updated_at",
    )
    list_select_related = ("importe_par",)
    date_hierarchy = "created_at"

    def has_add_permission(self, request) -> bool:
        return False


@admin.register(ImportCategories)
class ImportCategoriesAdmin(_ImportAdmin):
    pass


@admin.register(ImportProduits)
class ImportProduitsAdmin(_ImportAdmin):
    pass