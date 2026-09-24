"""API d'administration du système : config HTTPS/LDAP, accessible aux staff."""
import logging

from rest_framework import permissions, status, views
from rest_framework.response import Response

from .models import SystemConfig
from .serializers import SystemConfigSerializer
from .services import (
    generate_self_signed,
    test_ldap_connection,
    write_tls_files,
)

logger = logging.getLogger(__name__)


class SystemConfigView(views.APIView):
    """Lecture/écriture de la configuration système (HTTPS + LDAP)."""

    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]

    def get(self, request):
        return Response(SystemConfigSerializer(SystemConfig.get()).data)

    def patch(self, request):
        config = SystemConfig.get()
        serializer = SystemConfigSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        messages = []
        if any(k in serializer.validated_data for k in ("https_enabled", "https_domain", "tls_cert_pem", "tls_key_pem")):
            messages = write_tls_files(config)
            if serializer.validated_data.get("https_enabled") and not config.is_https_ready:
                messages.append(
                    "HTTPS activé sans certificat : terminaison TLS indisponible "
                    "tant qu'aucun certificat n'est fourni."
                )
        data = SystemConfigSerializer(config).data
        return Response({**data, "messages": messages})


class GenerateCertView(views.APIView):
    """Génère un certificat auto-signé (RSA 2048) pour le domaine configuré."""

    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]

    def post(self, request):
        config = SystemConfig.get()
        domain = (request.data.get("domain") or config.https_domain or "").strip()
        if not domain:
            return Response(
                {"ok": False, "message": "Le domaine HTTPS est requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        cert_pem, key_pem = generate_self_signed(domain)
        config.https_domain = domain
        config.tls_cert_pem = cert_pem
        config.tls_key_pem = key_pem
        config.save(update_fields=["https_domain", "tls_cert_pem", "tls_key_pem", "updated_at"])
        messages = write_tls_files(config)
        return Response(
            {
                "ok": True,
                "message": "Certificat auto-signé généré.",
                "messages": messages,
                "config": SystemConfigSerializer(config).data,
            }
        )


class TestLdapView(views.APIView):
    """Teste la connexion LDAP. Accepte un corps optionnel de valeurs à tester
    avant enregistrement (les champs reçus sont appliqués de façon éphémère)."""

    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]

    def post(self, request):
        config = SystemConfig.get()
        if request.data:
            # Application **en mémoire** des valeurs testées (aucune écriture en base).
            serializer = SystemConfigSerializer(config, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            for key, value in serializer.validated_data.items():
                setattr(config, key, value)
        return Response(test_ldap_connection(config))