"""Admin Django pour les modèles partagés (EF-11.1, EF-11.3)."""
from __future__ import annotations

from django.contrib import admin
from django.http import HttpRequest, HttpResponseRedirect
from django.urls import reverse

from general.models import Agence, ParametresEntreprise


@admin.register(Agence)
class AgenceAdmin(admin.ModelAdmin):
    list_display = ("nom", "telephone", "actif", "created_at")
    list_filter = ("actif",)
    search_fields = ("nom", "adresse", "telephone")
    prepopulated_fields = {"slug": ("nom",)}
    readonly_fields = ("created_at", "updated_at")
    ordering = ("nom",)


@admin.register(ParametresEntreprise)
class ParametresEntrepriseAdmin(admin.ModelAdmin):
    """Restreint à une seule instance : pas d'option "ajouter" une fois
    qu'un enregistrement existe (EF-11.3)."""

    list_display = ("nom", "devise", "email", "telephone")
    readonly_fields = ("created_at", "updated_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return not ParametresEntreprise.objects.exists()

    def has_delete_permission(self, request: HttpRequest, obj=None) -> bool:
        # Le modèle lève déjà PermissionError sur delete() (EF-11.3) ; on
        # bloque aussi l'action au niveau de l'admin pour ne pas l'afficher.
        return False

    def changelist_view(self, request: HttpRequest, extra_context=None):
        # Un seul enregistrement possible : on va directement au formulaire
        # de modification (ou de création s'il n'existe pas encore),
        # plutôt que d'afficher une liste à une seule ligne.
        obj = ParametresEntreprise.objects.first()
        if obj is not None:
            return HttpResponseRedirect(
                reverse("admin:general_parametresentreprise_change", args=[obj.pk])
            )
        return HttpResponseRedirect(reverse("admin:general_parametresentreprise_add"))