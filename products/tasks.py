"""Tâches Celery du catalogue produit (EF-2.3 : import de catégories)."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from celery import shared_task

from general.enums import ImportStatut

logger = logging.getLogger("shop.products")

REQUIRED_COLUMNS = {"nom"}
KNOWN_COLUMNS = {"nom", "parent", "actif"}


def _normalize_header(value: Any) -> str:
    return str(value or "").strip().lower()


def _to_bool(value: Any, default: bool = True) -> bool:
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "vrai", "oui", "yes", "y"}


@shared_task(bind=True)
def importer_categories(self, import_id: str) -> Dict[str, int]:
    """Traite un fichier Excel de catégories en arrière-plan (EF-2.3).

    Colonnes attendues (insensibles à la casse) :
      - nom     : obligatoire
      - parent  : nom de la catégorie parente, optionnel
      - actif   : optionnel, défaut vrai

    Les lignes sont traitées dans l'ordre du fichier, donc une catégorie
    peut servir de parent à une autre définie plus bas dans le même
    fichier. Chaque ligne réussie ou échouée est consignée dans
    ``ImportCategories.rapport`` pour le rapport de validation (EF-2.3).
    """
    # Import différé : évite un import circulaire au chargement de l'app
    # (products.models importe déjà des choses de general, pas l'inverse).
    import openpyxl

    from products.models import Categorie, ImportCategories

    import_obj = ImportCategories.objects.get(pk=import_id)
    import_obj.statut = ImportStatut.EN_COURS
    import_obj.save(update_fields=["statut", "updated_at"])

    rapport: List[Dict[str, Any]] = []
    reussies = 0
    echouees = 0

    try:
        workbook = openpyxl.load_workbook(import_obj.fichier.path, read_only=True, data_only=True)
        sheet = workbook.active
        rows = sheet.iter_rows(values_only=True)

        header = next(rows, None)
        if header is None:
            raise ValueError("Le fichier est vide.")

        columns = [_normalize_header(c) for c in header]
        missing = REQUIRED_COLUMNS - set(columns)
        if missing:
            raise ValueError(f"Colonne(s) manquante(s) : {', '.join(sorted(missing))}")

        col_index = {name: idx for idx, name in enumerate(columns) if name in KNOWN_COLUMNS}
        categories_par_nom = {c.nom.strip().lower(): c for c in Categorie.objects.all()}

        for ligne_num, row in enumerate(rows, start=2):
            if row is None or all(cell in (None, "") for cell in row):
                continue  # ligne vide, on l'ignore silencieusement

            nom_brut = row[col_index["nom"]] if col_index["nom"] < len(row) else None
            nom = str(nom_brut).strip() if nom_brut is not None else ""

            if not nom:
                echouees += 1
                rapport.append({
                    "ligne": ligne_num, "nom": None, "statut": "erreur",
                    "message": "Nom manquant.",
                })
                continue

            parent: Optional["Categorie"] = None
            if "parent" in col_index:
                parent_cell = row[col_index["parent"]] if col_index["parent"] < len(row) else None
                parent_nom = str(parent_cell).strip() if parent_cell else ""
                if parent_nom:
                    if parent_nom.lower() == nom.lower():
                        echouees += 1
                        rapport.append({
                            "ligne": ligne_num, "nom": nom, "statut": "erreur",
                            "message": "Une catégorie ne peut pas être son propre parent.",
                        })
                        continue
                    parent = categories_par_nom.get(parent_nom.lower())
                    if parent is None:
                        echouees += 1
                        rapport.append({
                            "ligne": ligne_num, "nom": nom, "statut": "erreur",
                            "message": f"Catégorie parente introuvable : « {parent_nom} ».",
                        })
                        continue

            actif = True
            if "actif" in col_index and col_index["actif"] < len(row):
                actif = _to_bool(row[col_index["actif"]], default=True)

            try:
                existante = categories_par_nom.get(nom.lower())
                if existante:
                    existante.parent = parent
                    existante.actif = actif
                    existante.save()
                    categorie = existante
                    action = "mise à jour"
                else:
                    categorie = Categorie.objects.create(nom=nom, parent=parent, actif=actif)
                    action = "créée"

                categories_par_nom[nom.lower()] = categorie
                reussies += 1
                rapport.append({
                    "ligne": ligne_num, "nom": nom, "statut": "ok",
                    "message": f"Catégorie {action}.",
                })
            except Exception as exc:  # noqa: BLE001 - on veut consigner toute erreur ligne par ligne
                echouees += 1
                rapport.append({"ligne": ligne_num, "nom": nom, "statut": "erreur", "message": str(exc)})

        import_obj.statut = ImportStatut.TERMINE

    except Exception as exc:  # noqa: BLE001 - erreur globale (fichier illisible, colonne manquante...)
        logger.exception("Échec de l'import de catégories %s", import_id)
        import_obj.statut = ImportStatut.ECHEC
        rapport.append({"ligne": None, "nom": None, "statut": "erreur", "message": str(exc)})

    import_obj.total_lignes = reussies + echouees
    import_obj.lignes_reussies = reussies
    import_obj.lignes_echouees = echouees
    import_obj.rapport = rapport
    import_obj.save()

    return {"reussies": reussies, "echouees": echouees}