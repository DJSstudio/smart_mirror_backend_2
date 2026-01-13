from django.core.management.base import BaseCommand
import os
import secrets

ENV_TEMPLATE = """
DJANGO_SECRET_KEY={secret}
DEBUG=1
ALLOWED_HOSTS=*
HOSTNAME=mirror-001
MIRROR_ID=mirror-001

DB_NAME=db/smart_mirror.db

MEDIA_ROOT=media/

TRANSFER_PRIVATE_KEY_PATH=keys/private.pem
TRANSFER_PUBLIC_KEY_PATH=keys/public.pem
TRANSFER_ALG=RS256
TRANSFER_EXP=120

APP_PORT=8000
PEER_DISCOVERY_PORT=5005
DISCOVERY_ENABLED=1
DISCOVERY_IP=
DISCOVERY_INTERVAL_SECONDS=10
DISCOVERY_USE_HOSTNAME=0
DISCOVERY_HOSTNAME=
DISCOVERY_HOSTNAME_SUFFIX=

LOG_LEVEL=INFO
"""

class Command(BaseCommand):
    help = "Generate .env file for Smart Mirror backend"

    def handle(self, *args, **kwargs):
        secret_key = secrets.token_hex(32)

        env_contents = ENV_TEMPLATE.format(secret=secret_key)

        if os.path.exists(".env"):
            self.stdout.write(self.style.WARNING(".env already exists! Not overwriting."))
            return

        with open(".env", "w") as f:
            f.write(env_contents)

        self.stdout.write(self.style.SUCCESS("✔ .env file created successfully!"))
