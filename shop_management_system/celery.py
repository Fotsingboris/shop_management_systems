"""Configuration Celery pour shop_management_system.

Démarrer un worker :  celery -A shop_management_system worker -l info
Démarrer beat (tâches planifiées) : celery -A shop_management_system beat -l info
"""
from __future__ import annotations

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "shop_management_system.settings")

app = Celery("shop_management_system")

# Toutes les clés CELERY_* de settings.py sont reprises automatiquement
# (namespace="CELERY" => CELERY_BROKER_URL devient broker_url, etc.)
app.config_from_object("django.conf:settings", namespace="CELERY")

# Découvre automatiquement un module tasks.py dans chaque app installée
# (general, users, products, sales) — pas besoin de les enregistrer à la main.
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Requête de debug : {self.request!r}")