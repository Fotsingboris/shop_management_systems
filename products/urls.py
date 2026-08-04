"""Routes de l'app products.

Si un products/urls.py existe déjà chez vous, fusionnez ces `path()`
dedans plutôt que d'écraser le fichier. Imports mis à jour pour pointer
vers `category_views`/`product_views` (noms réels de vos fichiers de
vues) ; remplacez par `views` si vous les regroupez dans un seul
`views.py`.
"""
from __future__ import annotations

from django.urls import path

from products.views import category_views, product_views
from products.views.stock_views import StockPriceCreateView, ProduitRechercheApiView, StockListView, StockUpdateView

app_name = "products"

urlpatterns = [
    # Catégories
    path("categories/", category_views.CategorieListView.as_view(), name="categorie_list"),
    path("categories/nouvelle/", category_views.CategorieCreateView.as_view(), name="categorie_create"),
    path(
        "categories/<uuid:pk>/modifier/",
        category_views.CategorieUpdateView.as_view(),
        name="categorie_update",
    ),
    path("categories/import/", category_views.CategorieImportView.as_view(), name="categorie_import"),
    path(
        "categories/import/modele/",
        category_views.CategorieImportTemplateView.as_view(),
        name="categorie_import_template",
    ),
    # Produits
    path("produits/", product_views.ProduitListView.as_view(), name="produit_list"),
    path("produits/nouveau/", product_views.ProduitCreateView.as_view(), name="produit_create"),
    path(
        "produits/<uuid:pk>/modifier/",
        product_views.ProduitUpdateView.as_view(),
        name="produit_update",
    ),
    path("produits/import/", product_views.ProduitImportView.as_view(), name="produit_import"),
    path(
        "produits/import/modele/",
        product_views.ProduitImportTemplateView.as_view(),
        name="produit_import_template",
    ),
    # Stock & prix par agence
    
    path("stock/", StockListView.as_view(), name="stock_list"),
    path("stock/ajouter/", StockPriceCreateView.as_view(), name="stock_create"),
    path("stock/<uuid:pk>/modifier/", StockUpdateView.as_view(), name="stock_update"),
    path(
        "stock/recherche-produits/",
        ProduitRechercheApiView.as_view(),
        name="stock_produit_recherche",
    ),
]