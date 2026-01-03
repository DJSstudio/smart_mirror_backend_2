from django.utils.deprecation import MiddlewareMixin

class ClientCertMiddleware(MiddlewareMixin):
    """
    Extracts client certificate information forwarded by a TLS-terminating proxy (e.g., Nginx).
    Fields are attached to request as:
      - request.client_cert
      - request.client_cn
    These can be used for peer mirror authentication.
    """

    def process_request(self, request):
        # Full PEM certificate if forwarded by proxy
        request.client_cert = (
            request.META.get("HTTP_X_SSL_CLIENT_CERT")
            or request.META.get("HTTP_SSL_CLIENT_CERT")
        )

        # Common Name (CN) extracted by proxy, useful for device identity checks
        request.client_cn = (
            request.META.get("HTTP_X_SSL_CLIENT_S_DN_CN")
            or request.META.get("HTTP_SSL_CLIENT_S_DN_CN")
        )
