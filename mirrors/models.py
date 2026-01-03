from django.db import models
import uuid
from django.utils import timezone

class Mirror(models.Model):
    """
    Represents a single mirror device running the Smart Mirror System.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hostname = models.CharField(max_length=128, unique=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    port = models.IntegerField(default=8000)
    public_key = models.TextField(blank=True, null=True)
    last_seen = models.DateTimeField(default=timezone.now)
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.hostname} ({self.id})"


# class Session(models.Model):
#     STATUS_CHOICES = (
#         ("active", "Active"),
#         ("transferring", "Transferring"),
#         ("transferred", "Transferred"),
#         ("ended", "Ended"),
#     )

#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     owner = models.ForeignKey(Mirror, on_delete=models.CASCADE, related_name="sessions")
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     # QR-login user metadata (avatar hash, username, anything)
#     user_meta = models.JSONField(default=dict, blank=True)

#     status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="active")
#     expiry = models.DateTimeField(null=True, blank=True)

#     def __str__(self):
#         return f"Session {self.id} owned by {self.owner.hostname}"

class Session(models.Model):
    STATUS_PENDING = "pending"
    STATUS_ACTIVE = "active"
    STATUS_ENDED = "ended"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending User Scan"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_ENDED, "Ended"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # keep your existing mirror FK line; adjust if your Mirror model path differs
    mirror = models.ForeignKey("mirrors.Mirror", on_delete=models.CASCADE)

    started_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    # existing boolean kept for backwards compatibility
    # is_active = models.BooleanField(default=False)

    # NEW fields for QR workflow
    qr_token_hash = models.CharField(max_length=128, unique=True, null=True, blank=True)
    qr_url = models.TextField(null=True, blank=True)

    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)

    device_id = models.CharField(max_length=128, null=True, blank=True)
    export_used = models.BooleanField(default=False)

    class Meta:
        ordering = ("-started_at",)

    @property
    def is_active(self):
        return self.status == self.STATUS_ACTIVE

    def mark_active(self, device_id: str | None = None):
        self.status = self.STATUS_ACTIVE
        self.activated_at = timezone.now()
        # self.is_active = True
        if device_id:
            self.device_id = device_id
        self.save(update_fields=["status", "activated_at", "device_id"])

    def mark_ended(self):
        self.status = self.STATUS_ENDED
        self.ended_at = timezone.now()
        # self.is_active = False
        self.save(update_fields=["status", "ended_at"])

    def __str__(self):
        return f"Session {self.id} ({self.status})"


class Video(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="videos")
    created_at = models.DateTimeField(auto_now_add=True)

    file = models.FileField(upload_to="videos/%Y/%m/%d/")
    thumbnail = models.ImageField(
        upload_to="thumbnails/%Y/%m/%d/",
        null=True,
        blank=True
    )

    size_bytes = models.BigIntegerField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)
    codec = models.CharField(max_length=64, default="h264")
    sha256 = models.CharField(max_length=64, blank=True)
    encrypted = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"Video {self.id} for Session {self.session_id}"


class TransferRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(Session, on_delete=models.CASCADE)
    from_mirror = models.ForeignKey(Mirror, on_delete=models.CASCADE, related_name="outgoing_transfers")
    to_mirror = models.ForeignKey(Mirror, on_delete=models.CASCADE, related_name="incoming_transfers")

    created_at = models.DateTimeField(auto_now_add=True)
    token = models.TextField()
    expires_at = models.DateTimeField()

    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    logs = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"Transfer {self.session_id}: {self.from_mirror.hostname} → {self.to_mirror.hostname}"
