from django.contrib import admin
from .models import Mirror, Session, Video, TransferRequest


@admin.register(Mirror)
class MirrorAdmin(admin.ModelAdmin):
    list_display = ("hostname", "ip", "port", "last_seen")
    search_fields = ("hostname", "ip")
    ordering = ("hostname",)


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "mirror",
        "status",
        "started_at",
        "activated_at",
        "ended_at",
    )

    list_filter = ("status", "mirror")

    search_fields = ("id", "mirror__hostname", "device_id")
    ordering = ("-started_at",)

    readonly_fields = (
        "started_at",
        "activated_at",
        "ended_at",
        "qr_token_hash",
        "qr_url",
    )


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "session",
        "created_at",
        "size_bytes",
        "duration_seconds",
        "codec",
        "encrypted",
    )
    list_filter = ("codec", "encrypted")
    search_fields = ("id", "session__id")
    ordering = ("-created_at",)


@admin.register(TransferRequest)
class TransferRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "session",
        "from_mirror",
        "to_mirror",
        "created_at",
        "expires_at",
        "completed",
    )
    list_filter = ("completed", "from_mirror", "to_mirror")
    search_fields = ("id", "session__id")
    ordering = ("-created_at",)
