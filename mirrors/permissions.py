# mirrors/models.py
from django.db import models
import uuid
from django.utils import timezone

class Mirror(models.Model):
    """
    Represents a single Mirror device (RK3568 device).
    Device certificates / metadata stored here for peer verification.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hostname = models.CharField(max_length=128, unique=True)  # device hostname or unique name
    ip = models.GenericIPAddressField(null=True, blank=True)
    port = models.IntegerField(default=8000)
    public_key = models.TextField(blank=True, null=True)  # PEM for verifying signed tokens if needed
    last_seen = models.DateTimeField(default=timezone.now)
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.hostname} ({self.id})"


class Session(models.Model):
    """
    A user 'session' — created on login via QR.
    """
    STATUS_CHOICES = (
        ("active", "Active"),
        ("transferring", "Transferring"),
        ("transferred", "Transferred"),
        ("ended", "Ended"),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(Mirror, on_delete=models.CASCADE, related_name="sessions")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user_meta = models.JSONField(default=dict, blank=True)  # e.g. user display name, avatar hash
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="active")
    expiry = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Session {self.id} @{self.owner}"


class Video(models.Model):
    """
    Metadata for a recorded video file belonging to a session.
    The actual file is stored under MEDIA_ROOT / videos/<mirror_id>/<session_id>
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="videos")
    created_at = models.DateTimeField(auto_now_add=True)
    file = models.FileField(upload_to="videos/%Y/%m/%d/")  # customize path in storage.py
    size_bytes = models.BigIntegerField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)
    codec = models.CharField(max_length=64, default="h264")
    sha256 = models.CharField(max_length=64, blank=True)  # integrity
    encrypted = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"Video {self.id} ({self.session_id})"


class TransferRequest(models.Model):
    """
    Tracks transfer requests between mirrors.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(Session, on_delete=models.CASCADE)
    from_mirror = models.ForeignKey(Mirror, on_delete=models.CASCADE, related_name="outgoing_transfers")
    to_mirror = models.ForeignKey(Mirror, on_delete=models.CASCADE, related_name="incoming_transfers")
    created_at = models.DateTimeField(auto_now_add=True)
    token = models.TextField()  # signed token issued by from_mirror
    expires_at = models.DateTimeField()
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    logs = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"Transfer {self.session_id} {self.from_mirror}->{self.to_mirror}"
