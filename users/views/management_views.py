"""Gestion des comptes utilisateurs par l'encadrement (EF-9).

Fichier séparé de ``auth_views.py`` (login/logout/écran de création de
compte "classique" déjà existant) : celui-ci porte l'écran de GESTION à
proprement parler — une liste avec recherche/filtres, et des modales de
création/modification/activation plutôt que des pages séparées, comme
demandé.

Convention adoptée pour "pas d'AJAX" (cohérente avec le reste du projet) :
les vues de création/modification sont des endpoints POST-only qui, en cas
d'erreur de validation, RÉ-AFFICHENT la page de liste complète avec le
formulaire invalide réinjecté et un indicateur (``modale_a_ouvrir``) que le
JS du template utilise pour rouvrir automatiquement la bonne modale au
chargement de la page, plutôt que de dépendre d'un fragment renvoyé en
Ajax.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q, QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import ListView

from general.enums import Role
from general.models import Agence
from users.forms import UtilisateurCreationForm, UtilisateurUpdateForm
from users.models import Utilisateur
from users.services import get_utilisateurs_visibles


class UtilisateurAccessMixin(UserPassesTestMixin):
    """Réservé à l'encadrement : Admin (tous les comptes) ou Responsable d'agence (ses Caissiers)."""

    def test_func(self) -> bool:
        return getattr(self.request.user, "is_admin", False) or getattr(
            self.request.user, "is_responsable_agence", False
        )


class UtilisateurListView(LoginRequiredMixin, UtilisateurAccessMixin, ListView):
    """Liste des comptes gérables, avec recherche/filtres et les 3 modales (EF-9).

    ``select_related("agence")`` : évite une requête par ligne affichée.
    """

    model = Utilisateur
    template_name = "dashboard/pages/admin/users/utilisateur_list.html"
    context_object_name = "utilisateurs"
    paginate_by = 20

    def get_queryset(self) -> QuerySet[Utilisateur]:
        qs = (
            get_utilisateurs_visibles(self.request.user)
            .select_related("agence")
            .order_by("first_name", "last_name", "username")
        )

        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(username__icontains=q)
                | Q(email__icontains=q)
            )

        role = self.request.GET.get("role", "").strip()
        if role:
            qs = qs.filter(role=role)

        agence_id = self.request.GET.get("agence", "").strip()
        if agence_id:
            qs = qs.filter(agence_id=agence_id)

        statut = self.request.GET.get("statut", "").strip()
        if statut == "actif":
            qs = qs.filter(is_active=True)
        elif statut == "inactif":
            qs = qs.filter(is_active=False)

        return qs

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Préfixes distincts obligatoires : les deux formulaires partagent les
        # mêmes noms de champs (username, role, agence, ...) et cohabitent
        # dans le même document. Sans préfixe, Django génère le même id HTML
        # ("id_username") pour les deux modales, et `getElementById` ne
        # renverrait alors QUE le champ de la modale de création.
        context.setdefault("create_form", UtilisateurCreationForm(created_by=user, prefix="creation"))
        context.setdefault("update_form", UtilisateurUpdateForm(editeur=user, prefix="edition"))
        context["q"] = self.request.GET.get("q", "")
        context["role"] = self.request.GET.get("role", "")
        context["agence_id"] = self.request.GET.get("agence", "")
        context["statut"] = self.request.GET.get("statut", "")

        # Un Admin peut filtrer/assigner n'importe quel rôle et n'importe
        # quelle agence ; un Responsable ne gère QUE des Caissiers de sa
        # propre agence, ces filtres n'ont donc pas lieu d'être pour lui.
        context["est_admin"] = getattr(user, "is_admin", False)
        if context["est_admin"]:
            context["role_choices"] = Role.choices
            context["agences"] = Agence.objects.all().order_by("nom")

        return context


def _reafficher_liste_avec_erreur(
    request: HttpRequest,
    *,
    create_form: Optional[UtilisateurCreationForm] = None,
    update_form: Optional[UtilisateurUpdateForm] = None,
    modale_a_ouvrir: str = "",
    update_pk: str = "",
) -> HttpResponse:
    """Ré-affiche la liste complète avec un formulaire invalide + la modale à rouvrir.

    Évite de dupliquer toute la logique de ``UtilisateurListView`` : on
    réutilise directement son ``get_queryset``/``get_context_data``.
    """
    vue = UtilisateurListView()
    vue.request = request
    vue.kwargs = {}
    vue.object_list = vue.get_queryset()

    # On ne passe que le formulaire réellement invalide : l'autre doit
    # rester absent des kwargs pour que `get_context_data` lui applique son
    # `setdefault` (un formulaire non lié "propre", avec le bon préfixe),
    # plutôt que de forcer explicitement `None` et casser le rendu de sa
    # modale (champs manquants) sur cette page ré-affichée.
    kwargs: Dict[str, Any] = {}
    if create_form is not None:
        kwargs["create_form"] = create_form
    if update_form is not None:
        kwargs["update_form"] = update_form

    context = vue.get_context_data(**kwargs)
    context["modale_a_ouvrir"] = modale_a_ouvrir
    context["update_pk"] = update_pk
    return vue.render_to_response(context)


class UtilisateurCreateModalView(LoginRequiredMixin, UtilisateurAccessMixin, View):
    """Traite la soumission de la modale "Nouvel utilisateur" (EF-9.1 à EF-9.4)."""

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        form = UtilisateurCreationForm(request.POST, created_by=request.user, prefix="creation")
        if form.is_valid():
            utilisateur = form.save()
            messages.success(
                request,
                _("Utilisateur « %(nom)s » créé avec succès.")
                % {"nom": utilisateur.get_full_name() or utilisateur.username},
            )
            return redirect("users:utilisateur_list")

        return _reafficher_liste_avec_erreur(request, create_form=form, modale_a_ouvrir="creation")


class UtilisateurUpdateModalView(LoginRequiredMixin, UtilisateurAccessMixin, View):
    """Traite la soumission de la modale "Modifier l'utilisateur" (EF-9.1 à EF-9.4).

    Repart de ``get_utilisateurs_visibles`` pour la revalidation serveur :
    un Responsable qui tente de modifier un compte hors de son périmètre
    (un autre Responsable, un Admin, un Caissier d'une autre agence) reçoit
    un 404 propre.
    """

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        utilisateur = get_object_or_404(get_utilisateurs_visibles(request.user), pk=kwargs["pk"])
        form = UtilisateurUpdateForm(
            request.POST, instance=utilisateur, editeur=request.user, prefix="edition"
        )
        if form.is_valid():
            form.save()
            messages.success(
                request,
                _("Utilisateur « %(nom)s » mis à jour.")
                % {"nom": utilisateur.get_full_name() or utilisateur.username},
            )
            return redirect("users:utilisateur_list")

        return _reafficher_liste_avec_erreur(
            request, update_form=form, modale_a_ouvrir="edition", update_pk=str(utilisateur.pk)
        )


class UtilisateurToggleActifView(LoginRequiredMixin, UtilisateurAccessMixin, View):
    """Active ou désactive un compte (EF-9).

    La désactivation est confirmée côté client par une modale avant l'envoi
    (voir utilisateur_list.html) — geste aux conséquences plus lourdes
    qu'une réactivation, qui elle reste une action directe en un clic.
    Un utilisateur ne peut jamais désactiver son propre compte (blocage
    immédiat de sa propre session sinon).
    """

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        utilisateur = get_object_or_404(get_utilisateurs_visibles(request.user), pk=kwargs["pk"])

        if utilisateur.pk == request.user.pk:
            messages.error(request, _("Vous ne pouvez pas désactiver votre propre compte."))
            return redirect("users:utilisateur_list")

        utilisateur.is_active = not utilisateur.is_active
        utilisateur.save(update_fields=["is_active", "updated_at"])

        libelle = "activé" if utilisateur.is_active else "désactivé"
        messages.success(
            request,
            _("Compte de %(nom)s %(libelle)s.")
            % {"nom": utilisateur.get_full_name() or utilisateur.username, "libelle": libelle},
        )
        return redirect("users:utilisateur_list")