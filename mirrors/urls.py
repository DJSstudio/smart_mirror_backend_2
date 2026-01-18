from django.urls import path
from .views import (
    SessionStartView,
    SessionEndView,
    VideoUploadView,
    VideoListView,
    VideoDetailView,
    VideoDeleteView,
    PeerSessionsView,
    TransferSessionRequestView,
    TransferSessionCompleteView,
    TransferSessionSnapshotView,
    TransferSessionFinalizeView,
    QRSessionCreateView,
    QRSessionActivateView,
    QRActivationHTMLView,
    QRSessionStatusView,
    StartRecordingView,
    StopRecordingView,
    ExportTokenView, 
    ExportDownloadView,
)

urlpatterns = [
    path("session/start", SessionStartView.as_view(), name="session_start"),
    path("session/end", SessionEndView.as_view(), name="session_end"),
    path("session/qr/create", QRSessionCreateView.as_view()),
    path("session/qr/activate", QRSessionActivateView.as_view()),
    path("qr/activate", QRActivationHTMLView.as_view(), name = "qr_activation_html"),
    path("session/qr/status", QRSessionStatusView.as_view()),

    path("videos/upload", VideoUploadView.as_view(), name="videos_upload"),
    path("videos/list", VideoListView.as_view(), name="videos_list"),
    path("videos/<uuid:pk>", VideoDetailView.as_view(), name="video_detail"),
    path("videos/delete", VideoDeleteView.as_view()),

    path("peer/sessions", PeerSessionsView.as_view(), name="peer_sessions"),

    path("transfer_session_request", TransferSessionRequestView.as_view(), name="transfer_request"),
    path("transfer_session_complete", TransferSessionCompleteView.as_view(), name="transfer_complete"),
    path("transfer_session_snapshot", TransferSessionSnapshotView.as_view(), name="transfer_snapshot"),
    path("transfer_session_finalize", TransferSessionFinalizeView.as_view(), name="transfer_finalize"),

    path("record/start", StartRecordingView.as_view()),
    path("record/stop", StopRecordingView.as_view()),

    path("export/token", ExportTokenView.as_view()),
    path("export", ExportDownloadView.as_view()),

]
