import json
import logging
import socket
import threading
import time
from ipaddress import ip_address
from urllib.parse import urlparse

from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone

from .models import Mirror

_LOG = logging.getLogger(__name__)
_thread = None
_stop_event = threading.Event()


def start_discovery_service() -> None:
    if not getattr(settings, "DISCOVERY_ENABLED", False):
        return
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop_event.clear()
    _thread = threading.Thread(
        target=_serve_loop,
        name="mirror-discovery",
        daemon=True,
    )
    _thread.start()


def stop_discovery_service() -> None:
    _stop_event.set()


def _serve_loop() -> None:
    announce_port = getattr(settings, "DISCOVERY_ANNOUNCE_PORT", 5005)
    interval = getattr(settings, "DISCOVERY_INTERVAL_SECONDS", 10)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except Exception:
        pass

    try:
        sock.bind(("", announce_port))
    except Exception as exc:
        _LOG.warning("Discovery bind failed on %s: %s", announce_port, exc)
        return

    sock.settimeout(1.0)
    next_announce = 0.0

    while not _stop_event.is_set():
        now = time.monotonic()
        if now >= next_announce:
            _send_announce(sock, announce_port)
            next_announce = now + interval

        try:
            data, addr = sock.recvfrom(4096)
        except socket.timeout:
            continue
        except Exception as exc:
            _LOG.debug("Discovery recv failed: %s", exc)
            continue

        _handle_datagram(sock, data, addr)

    sock.close()


def _send_announce(sock: socket.socket, announce_port: int) -> None:
    payload = _build_payload()
    data = json.dumps(payload).encode("utf-8")
    try:
        sock.sendto(data, ("255.255.255.255", announce_port))
    except Exception as exc:
        _LOG.debug("Discovery broadcast failed: %s", exc)


def _handle_datagram(sock: socket.socket, data: bytes, addr: tuple[str, int]) -> None:
    try:
        payload = json.loads(data.decode("utf-8"))
    except Exception:
        return

    if isinstance(payload, dict):
        msg_type = payload.get("type")
        if msg_type == "discover":
            _send_unicast(sock, addr, _build_payload())
            return

        if "mirror_id" in payload or "hostname" in payload:
            _update_peer_from_payload(payload, addr[0])


def _send_unicast(sock: socket.socket, addr: tuple[str, int], payload: dict) -> None:
    try:
        data = json.dumps(payload).encode("utf-8")
        sock.sendto(data, addr)
    except Exception as exc:
        _LOG.debug("Discovery response failed: %s", exc)


def _update_peer_from_payload(payload: dict, fallback_ip: str) -> None:
    mirror_id = payload.get("mirror_id")
    hostname = payload.get("hostname") or mirror_id
    if not hostname:
        return

    if mirror_id and mirror_id == getattr(settings, "MIRROR_ID", settings.HOSTNAME):
        return
    if hostname == settings.HOSTNAME:
        return

    ip_value = payload.get("ip") or fallback_ip
    ip_value = ip_value if _is_ip(ip_value) else fallback_ip

    port_value = payload.get("port")
    port = int(port_value) if isinstance(port_value, (int, float)) else _get_backend_port()

    meta = payload.get("metadata")
    if not isinstance(meta, dict):
        meta = {}
    if mirror_id:
        meta["mirror_id"] = mirror_id

    close_old_connections()
    Mirror.objects.update_or_create(
        hostname=hostname,
        defaults={
            "ip": ip_value,
            "port": port,
            "last_seen": timezone.now(),
            "metadata": meta,
        },
    )


def _build_payload() -> dict:
    ip = _get_advertised_ip() or "0.0.0.0"
    port = _get_backend_port()
    base_url = _get_base_url(ip, port)
    return {
        "type": "announce",
        "mirror_id": getattr(settings, "MIRROR_ID", settings.HOSTNAME),
        "hostname": settings.HOSTNAME,
        "ip": ip,
        "port": port,
        "base_url": base_url,
        "timestamp": int(time.time()),
    }


def _get_base_url(ip: str, port: int) -> str:
    base = settings.PUBLIC_BASE_URL
    if base:
        return _normalize_base_url(base)

    host_base = _get_hostname_base()
    if host_base:
        return _normalize_base_url(f"http://{host_base}:{port}")

    return _normalize_base_url(f"http://{ip}:{port}")


def _get_hostname_base() -> str | None:
    override = getattr(settings, "DISCOVERY_HOSTNAME", "")
    if override:
        return override

    if not getattr(settings, "DISCOVERY_USE_HOSTNAME", False):
        return None

    hostname = settings.HOSTNAME
    if not hostname:
        return None
    suffix = getattr(settings, "DISCOVERY_HOSTNAME_SUFFIX", "")
    if suffix and "." not in hostname:
        return f"{hostname}{suffix}"
    return hostname


def _normalize_base_url(base: str) -> str:
    trimmed = base.strip().rstrip("/")
    if not trimmed.startswith("http://") and not trimmed.startswith("https://"):
        trimmed = f"http://{trimmed}"
    if trimmed.endswith("/api"):
        return trimmed
    return f"{trimmed}/api"


def _get_backend_port() -> int:
    host, port = _parse_host_port(settings.PUBLIC_BASE_URL)
    if port:
        return port
    host, port = _parse_host_port(settings.DEVICE_IP)
    if port:
        return port
    return getattr(settings, "APP_PORT", 8000)


def _get_advertised_ip() -> str | None:
    if getattr(settings, "DISCOVERY_IP", ""):
        return settings.DISCOVERY_IP

    host, _ = _parse_host_port(settings.PUBLIC_BASE_URL)
    if host and _is_ip(host):
        return host

    host, _ = _parse_host_port(settings.DEVICE_IP)
    if host and _is_ip(host):
        return host

    return _get_local_ip()


def _parse_host_port(value: str) -> tuple[str | None, int | None]:
    if not value:
        return None, None
    if "://" in value:
        parsed = urlparse(value)
        host = parsed.hostname
        port = parsed.port
        return host, port
    if "/" in value:
        value = value.split("/", 1)[0]
    if ":" in value:
        host, raw_port = value.rsplit(":", 1)
        try:
            return host, int(raw_port)
        except ValueError:
            return host, None
    return value, None


def _is_ip(value: str) -> bool:
    try:
        ip_address(value)
        return True
    except ValueError:
        return False


def _get_local_ip() -> str | None:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass

    try:
        host = socket.gethostbyname(socket.gethostname())
        if host and not host.startswith("127."):
            return host
    except Exception:
        pass

    return None
