import os
import sys
from django.apps import AppConfig
from django.conf import settings

class MirrorsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "mirrors"

    def ready(self):
        if not getattr(settings, "DISCOVERY_ENABLED", False):
            return
        if not _should_start_discovery():
            return
        from .discovery import start_discovery_service

        start_discovery_service()


def _should_start_discovery() -> bool:
    run_main = os.environ.get("RUN_MAIN")
    if run_main is not None and run_main != "true":
        return False

    argv = " ".join(sys.argv).lower()
    if "runserver" in argv:
        return True
    if any(cmd in argv for cmd in ("gunicorn", "uwsgi", "daphne", "uvicorn")):
        return True
    return False
