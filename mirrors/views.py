from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
import hashlib
from pathlib import Path
import subprocess
import uuid

from .models import Mirror, Session, Video, TransferRequest

from .serializers import (
    SessionSerializer,
    VideoSerializer,
    MirrorSerializer,
)
from .tokens import generate_transfer_token, validate_transfer_token
from .utils import (
    generate_qr_token,
    generate_export_token,
    validate_export_token,
    generate_video_thumbnail,
    get_video_duration_seconds,
    get_public_base_url,
)



# -------------------------------------------
# Helper: Get or create this device's Mirror
# -------------------------------------------
def get_local_mirror():
    print("DEBUG: Resolving local mirror using HOSTNAME =", settings.HOSTNAME)

    hostname = settings.HOSTNAME
    mirror, created = Mirror.objects.get_or_create(
        hostname=hostname,
        defaults={"ip": None, "port": 8000}
    )

    if created:
        print("DEBUG: Created new Mirror entry:", mirror)
    else:
        print("DEBUG: Using existing Mirror entry:", mirror)

    return mirror



# -------------------------------------------
#  SESSION START
# -------------------------------------------
class SessionStartView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        mirror = get_local_mirror()
        user_meta = request.data.get("user_meta", {})
        expiry_seconds = int(request.data.get("expiry_seconds", 3600))

        session = Session.objects.create(
            mirror=mirror,
            user_meta=user_meta,
            expiry=timezone.now() + timedelta(seconds=expiry_seconds)
        )

        return Response(SessionSerializer(session).data, status=status.HTTP_201_CREATED)


# -------------------------------------------
# QR SESSION CREATE
# -------------------------------------------
class QRSessionCreateView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        print("\n===================================")
        print("DEBUG: QRSessionCreateView POST CALLED")
        print("Request META:", request.META.get("REMOTE_ADDR"))
        print("===================================\n")

        mirror = get_local_mirror()

        Session.objects.filter(
            mirror=mirror,
            status__in=[Session.STATUS_ACTIVE, Session.STATUS_PENDING],
        ).update(
            status=Session.STATUS_ENDED,
            ended_at=timezone.now(),
        )

        print("DEBUG: Mirror resolved:", mirror)

        raw_token, hashed = generate_qr_token()
        print("DEBUG: QR raw token:", raw_token)
        print("DEBUG: QR hashed token:", hashed)

        base_url = get_public_base_url(request)
        if not base_url:
            base_url = f"http://{settings.DEVICE_IP}"

        qr_url = f"{base_url}/api/qr/activate?token={raw_token}"

        print("DEBUG: Generated QR URL =", qr_url)

        try:
            session = Session.objects.create(
                mirror=mirror,
                qr_token_hash=hashed,
                qr_url=qr_url,
                status=Session.STATUS_PENDING,
            )
            print("DEBUG: Session created successfully:", session.id)

        except Exception as e:
            print("ERROR: Failed to create Session:", str(e))
            return Response({"error": str(e)}, status=500)

        response_data = {
            "session_id": str(session.id),
            "qr_url": qr_url,
            "qr_status": session.status,
            "qr_token": raw_token,  # Include raw token for reactivation
        }
        print("DEBUG: Returning JSON:", response_data)

        return Response(response_data, status=201)

# -------------------------------------------
# QR SESSION ACTIVATE
# -------------------------------------------

class QRSessionActivateView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        raw_token = request.query_params.get("token")
        device_id = request.query_params.get("device_id")

        if not raw_token or not device_id:
            return Response({"detail": "Missing token or device_id"}, status=400)

        print(f"🔐 QR Activation: token={raw_token[:20]}... device_id={device_id}")

        hashed = hashlib.sha256(raw_token.encode()).hexdigest()
        
        # Re-attach existing session
        existing = Session.objects.filter(
            device_id=device_id
        ).order_by("-started_at").first()

        if existing:
            print(f"✅ Found existing session {existing.id} for device {device_id}")
            existing.status = Session.STATUS_ACTIVE
            existing.activated_at = timezone.now()
            existing.save(update_fields=["status", "activated_at"])

            return Response({
                "session_id": str(existing.id),
                "status": "active",
                "type": "resumed"
            })

        try:
            session = Session.objects.get(
                qr_token_hash=hashed,
                status=Session.STATUS_PENDING
            )
        except Session.DoesNotExist:
            return Response({"detail": "Invalid or expired QR"}, status=400)

        print(f"✅ Activating new session {session.id} with device_id={device_id}")
        session.mark_active(device_id=device_id)

        return Response({
            "session_id": str(session.id),
            "status": "active",
            "type": "new"
        })


# class QRActivationHTMLView(APIView):
#     permission_classes = [permissions.AllowAny]

#     def get(self, request):
#         token = request.query_params.get("token")
#         if not token:
#             return HttpResponse("Invalid QR", status=400)

#         html = f"""
#         <!DOCTYPE html>
#         <html>
#         <head>
#             <meta name="viewport" content="width=device-width, initial-scale=1.0">
#             <title>Smart Mirror</title>
#         </head>
#         <body style="font-family:Arial;text-align:center;padding:40px;">
#             <h2>Connect to Smart Mirror</h2>
#             <p>Tap the button below to continue</p>

#             <button style="font-size:18px;padding:12px 24px;"
#                     onclick="activate()">Connect</button>

#             <script>
#                 function activate() {{
#                     let device_id = localStorage.getItem("mirror_device_id");

#                     if (!device_id) {{
#                         device_id = crypto.randomUUID();
#                         localStorage.setItem("mirror_device_id", device_id);
#                     }}

#                     fetch("/api/session/qr/activate?token={token}&device_id=" + device_id)
#                       .then(res => res.json())
#                       .then(() => {{
#                           document.body.innerHTML = "<h3>Connected ✔</h3>";
#                       }})
#                       .catch(() => {{
#                           document.body.innerHTML = "<h3>Error</h3>";
#                       }});
#                 }}
#             </script>
#         </body>
#         </html>
#         """
#         return HttpResponse(html)

class QRActivationHTMLView(APIView):
    permission_classes = [permissions.AllowAny]
    def get(self, request):
        token = request.query_params.get("token")
        device_id = request.query_params.get("device_id")

        if not token:
            return HttpResponse("Invalid QR")

        # If device_id is provided (e.g., from Flutter app), handle it as JSON API
        if device_id:
            return QRSessionActivateView().get(request)

        # If no device_id, serve HTML page for browser to use localStorage
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Smart Mirror — Connect</title>
            <style>body{{font-family:Arial;text-align:center;padding:40px;}}</style>
        </head>
        <body>
            <h2>Connect to Smart Mirror</h2>
            <p>Completing connection…</p>
            <div id="status">Connecting...</div>
            <script>
                (async function() {{
                    try {{
                        let key = 'mirror_device_id';
                        let device_id = localStorage.getItem(key);
                        if (!device_id) {{
                            if (window.crypto && crypto.randomUUID) {{
                                device_id = crypto.randomUUID();
                            }} else {{
                                device_id = 'web-' + Math.random().toString(36).slice(2, 10);
                            }}
                            localStorage.setItem(key, device_id);
                        }}

                        const resp = await fetch('/api/qr/activate?token={token}&device_id=' + encodeURIComponent(device_id));
                        const statusEl = document.getElementById('status');
                        if (!resp.ok) {{
                            const body = await resp.json().catch(() => ({{}}));
                            statusEl.innerText = 'Activation failed: ' + (body.detail || resp.status);
                            return;
                        }}
                        const data = await resp.json();
                        statusEl.innerText = 'Connected ✓';
                    }} catch (e) {{
                        document.getElementById('status').innerText = 'Error: ' + e;
                    }}
                }})();
            </script>
        </body>
        </html>
        """

        return HttpResponse(html)

    def _get_client_ip(self, request):
        """Get the client's IP address from the request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR', 'unknown')
        return ip



# -------------------------------------------
# QR SESSION STATUS
# -------------------------------------------


class QRSessionStatusView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        mirror = get_local_mirror()

        # 🔴 FIND THE TRUTH FROM DB, NOT FROM CLIENT
        session = Session.objects.filter(
            mirror=mirror,
            status=Session.STATUS_ACTIVE
        ).first()

        if not session:
            session = Session.objects.filter(
                mirror=mirror,
                status=Session.STATUS_PENDING
            ).order_by("-started_at").first()
            # return Response({
            #     "session_id": None,
            #     "qr_status": "none",
            #     "activated_at": None,
            # })

        return Response({
            "session_id": str(session.id),
            "qr_status": session.status,
            "activated_at": session.activated_at,
        })


# class QRSessionStatusView(APIView):
#     permission_classes = [permissions.AllowAny]

#     def get(self, request):
#         print("\n===================================")
#         print("DEBUG: QRSessionStatusView GET CALLED")
#         print("===================================\n")

#         session_id = request.query_params.get("id")
#         print("DEBUG: Checking session ID:", session_id)

#         # session = get_object_or_404(Session, pk=session_id)

#         mirror = get_local_mirror()
#         session = get_object_or_404(
#             Session,
#             pk=session_id,
#             mirror=mirror
#         )

#         response_data = {
#             "session_id": str(session.id),
#             "qr_status": session.status,
#             "activated_at": session.activated_at,
#         }

#         print("DEBUG: Returning session status:", response_data)

#         return Response(response_data)


# -------------------------------------------
#  SESSION END
# -------------------------------------------
class SessionEndView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        session_id = request.data.get("session_id")
        session = get_object_or_404(Session, pk=session_id)

        local = get_local_mirror()
        if session.mirror != local:
            return Response({"detail": "Not owner"}, status=status.HTTP_403_FORBIDDEN)

        session.status = "ended"
        session.save()

        return Response({"detail": "ended"}, status=status.HTTP_200_OK)


# -------------------------------------------
#  VIDEO UPLOAD
# -------------------------------------------
class VideoUploadView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        file = request.FILES.get("file")
        session_id = request.data.get("session_id")

        if not file or not session_id:
            return Response({"detail": "file and session_id required"}, status=400)

        session = get_object_or_404(Session, pk=session_id)
        local = get_local_mirror()

        if session.mirror != local:
            return Response({"detail": "Not owner of session"}, status=403)

        video = Video(session=session, file=file, size_bytes=file.size)
        video.save()

        # SHA256 checksum
        with video.file.open("rb") as f:
            sha = hashlib.sha256(f.read()).hexdigest()

        video.sha256 = sha
        duration_seconds = get_video_duration_seconds(video.file.path)
        if duration_seconds is not None:
            video.duration_seconds = duration_seconds
        video.save()

        return Response(VideoSerializer(video).data, status=201)


# -------------------------------------------
#  VIDEO LIST
# -------------------------------------------
class VideoListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        session_id = request.query_params.get("session_id")

        if session_id:
            videos = Video.objects.filter(session__id=session_id)
        else:
            videos = Video.objects.all()

        # Best-effort backfill for missing durations.
        for video in videos.filter(duration_seconds__isnull=True):
            duration_seconds = get_video_duration_seconds(video.file.path)
            if duration_seconds is not None:
                video.duration_seconds = duration_seconds
                video.save(update_fields=["duration_seconds"])

        return Response(
            VideoSerializer(
                videos,
                many=True,
                context={"request": request}
            ).data
        )



# -------------------------------------------
#  VIDEO DETAIL VIEW
# -------------------------------------------
class VideoDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, pk):
        video = get_object_or_404(Video, pk=pk)
        return Response(VideoSerializer(video).data)


# -------------------------------------------
#  PEER SESSIONS
# -------------------------------------------
class PeerSessionsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        local = get_local_mirror()

        mirror_data = MirrorSerializer(local).data
        sessions_data = SessionSerializer(
            local.sessions.filter(status="active"),
            many=True
        ).data

        return Response(
            {
                "mirror": mirror_data,
                "sessions": sessions_data,
            }
        )


# -------------------------------------------
#  SESSION TRANSFER — REQUEST TOKEN
# -------------------------------------------
class TransferSessionRequestView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        session_id = request.data.get("session_id")
        to_mirror_id = request.data.get("to_mirror_id")

        if not session_id or not to_mirror_id:
            return Response(
                {"detail": "session_id and to_mirror_id required"}, status=400
            )

        session = get_object_or_404(Session, pk=session_id)
        local = get_local_mirror()

        if session.mirror != local:
            return Response({"detail": "Not owner"}, status=403)

        to_mirror = get_object_or_404(Mirror, pk=to_mirror_id)

        exp = settings.TRANSFER_TOKEN.get("EXP_SECONDS", 120)
        token = generate_transfer_token(session_id, local.id, to_mirror_id, exp)

        transfer = TransferRequest.objects.create(
            session=session,
            from_mirror=local,
            to_mirror=to_mirror,
            token=token,
            expires_at=timezone.now() + timedelta(seconds=exp),
        )

        return Response({"token": token, "expires_at": transfer.expires_at}, status=201)


# -------------------------------------------
#  SESSION TRANSFER COMPLETE (receiver calls)
# -------------------------------------------
class TransferSessionCompleteView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        token = request.data.get("token")

        if not token:
            return Response({"detail": "token required"}, status=400)

        try:
            payload = validate_transfer_token(token)
        except Exception as e:
            return Response({"detail": f"Invalid token: {str(e)}"}, status=400)

        session_id = payload["sub"]
        to_mirror_id = payload["to"]
        from_mirror_id = payload["from"]

        local = get_local_mirror()

        if str(local.id) != str(to_mirror_id):
            return Response({"detail": "Token not for this mirror"}, status=403)

        # Create new session & metadata
        session_meta = request.data.get("session_metadata", {})
        new_session = Session.objects.create(
            id=session_id, owner=local, user_meta=session_meta
        )

        # Create placeholder video rows (files transferred separately)
        for v in request.data.get("video_metadata", []):
            Video.objects.create(
                session=new_session,
                size_bytes=v.get("size_bytes"),
                duration_seconds=v.get("duration_seconds"),
                codec=v.get("codec", "h264"),
                sha256=v.get("sha256", ""),
                encrypted=v.get("encrypted", True),
                metadata=v.get("metadata", {}),
            )

        # Mark transfer completed
        try:
            tr = TransferRequest.objects.get(
                session__id=session_id,
                from_mirror__id=from_mirror_id,
                to_mirror=local,
            )
            tr.completed = True
            tr.completed_at = timezone.now()
            tr.save()
        except TransferRequest.DoesNotExist:
            pass

        return Response({"detail": "transfer completed", "session_id": session_id}, status=201)


class VideoDeleteView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        video_id = request.data.get("id")
        if not video_id:
            return Response({"detail": "id required"}, status=400)

        video = get_object_or_404(Video, pk=video_id)
        video.delete()

        return Response({"detail": "deleted"})


class StartRecordingView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        session_id = request.data.get("session_id")
        if not session_id:
            return Response({"detail": "session_id required"}, status=400)

        print("🔴 RECORDING STARTED for session:", session_id)

        # In real system → trigger native agent
        return Response({"status": "recording_started"})


# class StopRecordingView(APIView):
#     permission_classes = [permissions.AllowAny]

#     def post(self, request):
#         print("DEBUG STOP:", request.FILES, request.data)

#         session_id = request.data.get("session_id")
#         file = request.FILES.get("file")  # MUST NOT BE NONE

#         if file is None:
#             return Response({"detail": "No video file received"}, status=400)

#         session = get_object_or_404(Session, pk=session_id)

#         video = Video.objects.create(
#             session=session,
#             file=file,
#             size_bytes=file.size
#         )

#         return Response({"status": "saved", "video_id": str(video.id)})


class StopRecordingView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        print("DEBUG STOP:", request.FILES, request.data)

        session_id = request.data.get("session_id")
        file = request.FILES.get("file")

        if not session_id:
            return Response({"detail": "session_id required"}, status=400)

        if file is None:
            return Response({"detail": "No video file received"}, status=400)

        session = get_object_or_404(Session, pk=session_id)

        # 1️⃣ Save video
        video = Video.objects.create(
            session=session,
            file=file,
            size_bytes=file.size
        )

        duration_seconds = get_video_duration_seconds(video.file.path)
        if duration_seconds is not None:
            video.duration_seconds = duration_seconds
            video.save(update_fields=["duration_seconds"])

        # 2️⃣ Generate thumbnail (best effort)
        try:
            video_path = Path(video.file.path)

            thumb_name = f"{uuid.uuid4().hex}.jpg"
            thumb_rel_path = Path("thumbnails") / thumb_name
            thumb_abs_path = Path(settings.MEDIA_ROOT) / thumb_rel_path

            thumb_abs_path.parent.mkdir(parents=True, exist_ok=True)

            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i", str(video_path),
                    "-ss", "00:00:01",
                    "-vframes", "1",
                    str(thumb_abs_path),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )

            video.thumbnail = str(thumb_rel_path)
            video.save(update_fields=["thumbnail"])

        except Exception as e:
            # ⚠️ Thumbnail failure should NOT block video save
            print("⚠️ Thumbnail generation failed:", e)

        return Response(
            {
                "status": "saved",
                "video_id": str(video.id),
                "thumbnail": video.thumbnail.url if video.thumbnail else None,
            },
            status=201,
        )


class ExportTokenView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        session_id = request.data.get("session_id")

        if not session_id:
            return Response(
                {"detail": "session_id required"},
                status=400
            )

        session = get_object_or_404(Session, pk=session_id)

        if session.status != Session.STATUS_ACTIVE:
            return Response({"detail": "Session not active"}, status=403)

        if not session.device_id:
            return Response({"detail": "Session not bound to device"}, status=403)

        # Generate export token tied to the device that activated the session
        token = generate_export_token(
            session_id=str(session.id),
            device_id=session.device_id,
        )

        base_url = get_public_base_url(request)
        if not base_url:
            base_url = f"http://{request.get_host()}"
        export_url = f"{base_url}/api/export?token={token}"
        print(f"✅ Export token generated for session {session.id} with device_id={session.device_id}")

        return Response({"export_url": export_url}, status=status.HTTP_200_OK)

class ExportDownloadView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        token = request.GET.get("token")
        if not token:
            return HttpResponseForbidden("Missing token")

        try:
            payload = validate_export_token(token)
            print(f"🔐 Export Download: token validated. session_id={payload['session_id']}, device_id={payload['device_id']}")
        except Exception as e:
            print(f"❌ Export Download: token validation failed: {e}")
            return HttpResponseForbidden("Invalid or expired token")

        session = get_object_or_404(Session, pk=payload["session_id"])

        # 🔒 TOKEN ↔ SESSION
        if session.device_id != payload["device_id"]:
            print(f"❌ Device mismatch! Session device_id={session.device_id}, Token device_id={payload['device_id']}")
            return HttpResponseForbidden("Device mismatch")

        print(f"✅ Device match confirmed. Proceeding with export for session {session.id}")

        # 🔒 ONE-TIME USE
        # if session.export_used:
        #     return HttpResponseForbidden("Export already used")

        # Mark export as used
        session.export_used = True
        session.save(update_fields=["export_used"])

        # videos = session.videos.all()
        # html = "<h2>Your Videos</h2><ul>"
        # for v in videos:
        #     html += f'<li><a href="{v.file.url}">{v.file.name}</a></li>'
        # html += "</ul>"

        # return HttpResponse(html)

        videos = session.videos.all()

        html = """
        <html>
        <head>
        <style>
            body { font-family: Arial; background: #111; color: white; }
            .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 16px; }
            .card { background: #222; padding: 8px; border-radius: 12px; }
            img { width: 100%; border-radius: 8px; }
            a { display: block; margin-top: 8px; text-align: center; color: #0af; text-decoration: none; }
        </style>
        </head>
        <body>
        <h2>Your Videos</h2>
        <div class="grid">
        """

        for v in videos:
            thumb = v.thumbnail.url if v.thumbnail else ""
            html += f"""
            <div class="card">
                <img src="{thumb}" />
                <a href="{v.file.url}" download>Download</a>
            </div>
            """

        html += "</div></body></html>"

        return HttpResponse(html)
