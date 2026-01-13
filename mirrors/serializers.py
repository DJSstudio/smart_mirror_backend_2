from rest_framework import serializers
from .models import Mirror, Session, Video, TransferRequest
from .utils import get_public_base_url

class MirrorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mirror
        fields = "__all__"


class SessionSerializer(serializers.ModelSerializer):
    mirror = MirrorSerializer(read_only=True)

    class Meta:
        model = Session
        fields = "__all__"
        read_only_fields = (
            "id",
            "started_at",
            "activated_at",
            "ended_at",
            "mirror",
            "status",
        )


class VideoSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = Video
        fields = "__all__"
        read_only_fields = ("id", "created_at", "sha256")

    def get_file_url(self, obj):
        request = self.context.get("request")
        base_url = get_public_base_url(request)
        if base_url:
            return f"{base_url}{obj.file.url}"

        from django.conf import settings
        return f"http://{settings.DEVICE_IP}{obj.file.url}"

    def get_thumbnail_url(self, obj):
        if not obj.thumbnail:
            return None

        request = self.context.get("request")
        base_url = get_public_base_url(request)
        if base_url:
            return f"{base_url}{obj.thumbnail.url}"

        from django.conf import settings
        return f"http://{settings.DEVICE_IP}{obj.thumbnail.url}"



class TransferRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransferRequest
        fields = "__all__"
        read_only_fields = ("id", "token", "created_at", "completed")
