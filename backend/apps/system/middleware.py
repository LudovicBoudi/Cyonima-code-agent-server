"""Middleware d'application à chaud de la politique HTTPS.

Dépend de `SystemConfig.https_enabled`. Placé juste après
`django.middleware.security.SecurityMiddleware` :
- redirige HTTP → HTTPS (en tenant compte de `X-Forwarded-Proto`) ;
- ajoute l'en-tête HSTS ;
- force l'attribut `Secure` sur tous les cookies émis.

En développement (`DEBUG=True`) et sur un hôte local (localhost / *.local), la
politique n'est **pas** appliquée pour ne pas casser l'UI Vite/daphne sans TLS.
"""
import re

from django.conf import settings
from django.http import HttpResponsePermanentRedirect

from .models import SystemConfig

_SET_COOKIE_RE = re.compile(r"([^;=\s]+=[^;]*)(;|$)", re.IGNORECASE)
_HSTS = "max-age=31536000; includeSubDomains"
_LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1", "0.0.0.0")


def _is_local_host(host: str) -> bool:
    host = (host or "").split(":")[0]
    return host in _LOCAL_HOSTS or host.endswith(".local") or host == "testserver"


class HttpsConfigMiddleware:
    """Applique la politique HTTPS définie en base (SystemConfig).

    La politique n'est **pas** appliquée :
    - lorsque la config HTTPS est désactivée en base ;
    - en développement local (DEBUG=True) et sur les hôtes locaux
      (localhost / *.local / testserver), pour ne pas casser l'UI Vite/daphne
      qui ne font pas de TLS.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            config = SystemConfig.get()
        except Exception:  # noqa: BLE001 — table pas encore migrée / base absente
            config = None
        enabled = bool(config and config.https_enabled)
        if (
            not enabled
            or settings.DEBUG
            or _is_local_host(request.get_host())
        ):
            return self.get_response(request)

        scheme = request.headers.get("x-forwarded-proto", request.scheme)
        if scheme == "http":
            url = request.build_absolute_uri().replace("http://", "https://", 1)
            return HttpResponsePermanentRedirect(url)

        response = self.get_response(request)
        if not response.has_header("Strict-Transport-Security"):
            response["Strict-Transport-Security"] = _HSTS
        return self._secure_cookies(response)

    @staticmethod
    def _secure_cookies(response) -> object:
        """Ajoute `; Secure` à chaque cookie set si absent (hors `HttpOnly`)."""
        try:
            cookies = response.cookies
        except AttributeError:
            return response
        for cookie in cookies.values():
            if not cookie.get("secure"):
                cookie["secure"] = True
        return response