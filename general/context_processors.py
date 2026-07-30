"""Context processors partagés par toute l'application (EF-10.2)."""
from __future__ import annotations

from typing import Any, Dict

from django.http import HttpRequest

from general.models import ParametresEntreprise


def parametres_entreprise(request: HttpRequest) -> Dict[str, Any]:
    """Injecte les paramètres de l'entreprise dans CHAQUE template.

    Évite que chaque vue ait à les transmettre explicitement dans son
    contexte (EF-10.2). ``ParametresEntreprise.load()`` est déjà mis en
    cache et invalidé à chaque sauvegarde (EF-10.3, EF-13.2), donc cet
    appel supplémentaire à chaque requête reste bon marché.

    Utilisation dans un template : ``{{ parametres.nom }}``,
    ``{{ parametres.logo.url }}``, ``{{ parametres.devise }}``...
    """
    return {"parametres": ParametresEntreprise.load()}