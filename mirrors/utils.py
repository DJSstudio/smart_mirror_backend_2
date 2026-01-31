# mirrors/utils.py
import secrets
import hashlib
import jwt
from datetime import datetime, timedelta
from typing import Optional
from django.conf import settings
import subprocess
from pathlib import Path

EXPORT_TOKEN_TTL_SECONDS = 600  # 10 minutes

def generate_qr_token():
    """
    Returns (raw_token, hashed_token).
    raw_token is short-lived and given in the QR URL (shown to the user).
    hashed_token is stored in DB for secure comparison.
    """
    raw = secrets.token_urlsafe(24)  # url-safe token to embed in QR
    hashed = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return raw, hashed


def generate_export_token(session_id: str, device_id: str) -> str:
    payload = {
        "session_id": session_id,
        "device_id": device_id,
        "exp": datetime.utcnow() + timedelta(seconds=EXPORT_TOKEN_TTL_SECONDS),
        "type": "export",
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm="HS256",
    )


def validate_export_token(token: str) -> dict:
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=["HS256"],
    )

def get_public_base_url(request=None):
    base = getattr(settings, "PUBLIC_BASE_URL", "") or ""
    if base:
        return _normalize_base_url(base)

    hostname_override = _get_hostname_override()
    if hostname_override:
        scheme = _get_request_scheme(request)
        host_port = _apply_port(hostname_override, _get_backend_port(request))
        return f"{scheme}://{host_port}"

    if request is None:
        return None

    scheme = _get_request_scheme(request)
    host = request.get_host()
    return f"{scheme}://{host}"


def _normalize_base_url(base: str) -> str:
    trimmed = base.strip().rstrip("/")
    if not trimmed:
        return ""
    if not trimmed.startswith("http://") and not trimmed.startswith("https://"):
        trimmed = f"http://{trimmed}"
    return trimmed


def _get_request_scheme(request=None) -> str:
    if request is None:
        return "http"
    scheme = "https" if request.is_secure() else "http"
    forwarded_proto = request.META.get("HTTP_X_FORWARDED_PROTO")
    if forwarded_proto:
        scheme = forwarded_proto.split(",")[0].strip()
    return scheme


def _get_backend_port(request=None) -> Optional[int]:
    port = getattr(settings, "APP_PORT", None)
    if port:
        try:
            return int(port)
        except (TypeError, ValueError):
            return None
    if request is None:
        return None
    try:
        return int(request.get_port())
    except (TypeError, ValueError):
        return None


def _apply_port(host: str, port: Optional[int]) -> str:
    if not host or not port:
        return host
    if ":" in host:
        return host
    if port in (80, 443):
        return host
    return f"{host}:{port}"


def _get_hostname_override() -> Optional[str]:
    override = getattr(settings, "DISCOVERY_HOSTNAME", "").strip()
    if override:
        return override

    if not getattr(settings, "DISCOVERY_USE_HOSTNAME", False):
        return None

    hostname = getattr(settings, "HOSTNAME", "").strip()
    if not hostname:
        return None

    suffix = getattr(settings, "DISCOVERY_HOSTNAME_SUFFIX", "").strip()
    if suffix and "." not in hostname:
        return f"{hostname}{suffix}"
    return hostname

def generate_video_thumbnail(video_path, output_path):
    subprocess.run([
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-ss", "00:00:01",
        "-vframes", "1",
        output_path
    ], check=True)

def get_video_duration_seconds(video_path):
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except Exception:
        return None

    try:
        return float(result.stdout.strip())
    except ValueError:
        return None
