"""Génération du reçu PDF d'une vente, via WeasyPrint (EF-8).

Fichier séparé (comme sales/services.py) : ni les vues ni les formulaires
n'ont besoin de savoir COMMENT le PDF est construit, seulement d'appeler
``generer_recu_pdf(commande)``.

Nécessite le paquet ``weasyprint`` :

    pip install weasyprint

WeasyPrint dépend lui-même de bibliothèques système (Pango, Cairo, GDK-
Pixbuf...) qui doivent être installées sur la machine de déploiement — voir
https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation
selon votre OS. L'import de ``weasyprint`` est fait à l'intérieur de la
fonction (pas en haut du fichier) pour que le reste du projet continue de
fonctionner même si le paquet n'est pas encore installé partout (dev local
sans le PDF, par exemple) ; seule la génération de reçu échouera tant qu'il
manque.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from django.core.files.base import ContentFile
from django.template.loader import render_to_string

from general.models import ParametresEntreprise
from sales.models import Commande, Recu


def generer_numero_recu(commande: Commande) -> str:
    """Numéro de reçu lisible et unique (EF-8.3) : date de la vente + 8 premiers
    caractères de son UUID, largement suffisant pour rester unique en pratique
    sans avoir besoin d'un compteur séquentiel partagé entre agences."""
    return f"REC-{commande.date:%Y%m%d}-{str(commande.id)[:8].upper()}"


def generer_recu_pdf(commande: Commande, *, base_url: Optional[str] = None) -> Recu:
    """Génère (ou régénère) le PDF du reçu d'une vente et l'attache au modèle Recu (EF-8.1, EF-8.2).

    Idempotent : si un Recu existe déjà pour cette commande (OneToOne), son
    fichier PDF est régénéré et remplacé plutôt que de dupliquer la ligne —
    utile pour régénérer un reçu après correction des paramètres de
    l'entreprise (EF-10), ou si la génération avait échoué au moment de la
    vente et qu'on la redéclenche depuis le bouton "Télécharger".

    ``base_url`` doit être l'URL absolue du site (ex. ``request.build_absolute_uri("/")``)
    pour que WeasyPrint puisse résoudre le logo de l'entreprise (chemin
    relatif ``/media/...``) en fichier réel.
    """
    from weasyprint import HTML  # import local, voir docstring du module

    # Le numéro de reçu doit exister AVANT de rendre le HTML (il est imprimé
    # dessus) : on crée/récupère la ligne Recu en premier, on ne l'attache
    # son fichier PDF qu'une fois celui-ci généré.
    recu, _created = Recu.objects.get_or_create(
        commande=commande,
        defaults={"numero_recu": generer_numero_recu(commande)},
    )

    parametres = ParametresEntreprise.load()
    lignes = list(commande.lignes.select_related("produit").all())
    sous_total = sum((ligne.sous_total for ligne in lignes), Decimal("0"))
    html_content = render_to_string(
        "dashboard/pages/admin/sales/pdf/recu.html",
        {
            "commande": commande,
            "recu": recu,
            "lignes": lignes,
            "sous_total": sous_total,
            "parametres": parametres,
        },
    )
    pdf_bytes = HTML(string=html_content, base_url=base_url).write_pdf()
    recu.fichier_pdf.save(f"{recu.numero_recu}.pdf", ContentFile(pdf_bytes), save=True)
    return recu