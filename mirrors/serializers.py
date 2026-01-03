from rest_framework import serializers
from .models import Mirror, Session, Video, TransferRequest

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

    class Meta:
        model = Video
        fields = "__all__"
        read_only_fields = ("id", "created_at", "sha256")

    def get_file_url(self, obj):
        request = self.context.get("request")
        if request is None:
            return obj.file.url
        return request.build_absolute_uri(obj.file.url)



class TransferRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransferRequest
        fields = "__all__"
        read_only_fields = ("id", "token", "created_at", "completed")
