"""Routes de l'app products.

Si un products/urls.py existe déjà chez vous, fusionnez ces `path()`
dedans plutôt que d'écraser le fichier.
"""
from __future__ import annotations

from django.urls import path

from products.views.category_views import CategorieListView, CategorieCreateView, CategorieImportView, CategorieImportTemplateView, CategorieUpdateView

app_name = "products"

urlpatterns = [
    path("categories/", CategorieListView.as_view(), name="categorie_list"),
    path("categories/nouvelle/", CategorieCreateView.as_view(), name="categorie_create"),
    path("categories/import/", CategorieImportView.as_view(), name="categorie_import"),
    path(
        "categories/<uuid:pk>/modifier/",
        CategorieUpdateView.as_view(),
        name="categorie_update",
    ),
    path(
        "categories/import/modele/",
        CategorieImportTemplateView.as_view(),
        name="categorie_import_template",
    ),
]