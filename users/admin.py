"""Admin Django pour les utilisateurs et leurs sous-types par rôle (EF-11.1)."""
from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm
from django.utils.translation import gettext_lazy as _

from users.forms import UtilisateurCreationForm
from users.models import Admin, Caissier, ResponsableAgence, Utilisateur


class UtilisateurChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = Utilisateur


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    """Vue d'ensemble : tous les utilisateurs, tous rôles confondus (EF-11.1).

    Réutilise UserAdmin (formulaires, hachage du mot de passe, écran de
    changement de mot de passe...) plutôt que ModelAdmin nu, puisque
    Utilisateur hérite d'AbstractUser.
    """

    add_form = UtilisateurCreationForm
    form = UtilisateurChangeForm
    model = Utilisateur

    list_display = ("username", "nom_complet", "email", "role", "agence", "is_active", "is_staff")
    list_filter = ("role", "agence", "is_active", "is_staff", "is_superuser")
    search_fields = ("username", "first_name", "last_name", "email", "telephone")
    ordering = ("username",)
    readonly_fields = ("created_at", "updated_at")

    # Déclarés explicitement (plutôt qu'en étendant UserAdmin.fieldsets /
    # add_fieldsets) pour ne pas hériter de champs propres à l'admin/forms
    # historiques d'auth.User qui n'existent pas forcément sur nos formulaires
    # personnalisés (ex: le champ "usable_password" ajouté par Django 5.1+).
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (_("Informations personnelles"), {"fields": ("first_name", "last_name", "email", "telephone")}),
        (_("Informations métier"), {"fields": ("role", "agence")}),
        (_("Permissions"), {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        (_("Dates importantes"), {"fields": ("last_login", "date_joined")}),
        (_("Traçabilité"), {"fields": ("created_at", "updated_at")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "password1", "password2", "role", "agence", "telephone", "email"),
        }),
    )

    @admin.display(description=_("Nom complet"))
    def nom_complet(self, obj: Utilisateur) -> str:
        return obj.get_full_name() or "—"


class _RoleProxyAdmin(UtilisateurAdmin):
    """Base commune aux admins des proxies de rôle (Admin, ResponsableAgence, Caissier).

    Chaque proxy a son propre manager (AdminManager, ResponsableAgenceManager,
    CaissierManager) qui filtre déjà le queryset par rôle (voir users/models.py) :
    chaque écran n'affiche donc que les utilisateurs de ce rôle, sans filtrage
    supplémentaire à écrire ici.
    """


@admin.register(Admin)
class AdminUtilisateurAdmin(_RoleProxyAdmin):
    list_filter = ("agence", "is_active", "is_staff", "is_superuser")


@admin.register(ResponsableAgence)
class ResponsableAgenceAdmin(_RoleProxyAdmin):
    list_filter = ("agence", "is_active")


@admin.register(Caissier)
class CaissierAdmin(_RoleProxyAdmin):
    list_filter = ("agence", "is_active")