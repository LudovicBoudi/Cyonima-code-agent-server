from rest_framework import serializers

from .models import SystemConfig


class SystemConfigSerializer(serializers.ModelSerializer):
    """Représentation côté admin. Secrets en write-only (jamais réémis)."""

    has_tls_cert = serializers.SerializerMethodField()
    is_https_ready = serializers.SerializerMethodField()

    class Meta:
        model = SystemConfig
        fields = [
            # HTTPS
            "https_enabled",
            "https_domain",
            "tls_cert_pem",
            "tls_key_pem",
            "has_tls_cert",
            "is_https_ready",
            # LDAP
            "ldap_enabled",
            "ldap_type",
            "ldap_server_uri",
            "ldap_bind_dn",
            "ldap_bind_password",
            "ldap_base_dn",
            "ldap_login_attribute",
            "ldap_user_filter",
            "ldap_email_domain",
            "ldap_start_tls",
            "ldap_user_attr",
        ]
        read_only_fields = ["has_tls_cert", "is_https_ready"]
        extra_kwargs = {
            "tls_cert_pem": {"write_only": True, "required": False, "allow_blank": True},
            "tls_key_pem": {"write_only": True, "required": False, "allow_blank": True},
            "ldap_bind_password": {"write_only": True, "required": False, "allow_blank": True},
        }

    def get_has_tls_cert(self, obj):
        return obj.is_https_ready

    def get_is_https_ready(self, obj):
        return obj.is_https_ready