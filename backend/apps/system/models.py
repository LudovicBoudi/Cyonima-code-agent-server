import logging

from django.contrib.auth import get_user_model
from django.db import models

logger = logging.getLogger(__name__)


class SystemConfig(models.Model):
    """Configuration unique (singleton, pk=1) modifiable par l'admin à chaud.

    Les certificats PEM sont stockés en texte dans la base pour être portables ;
    ils sont matérialisés sur disque (`data/tls/`) à l'enregistrement pour être
    utilisables par nginx/daphne.
    """

    class LdapType(models.TextChoices):
        AD = "ad", "Active Directory"
        OPENLDAP = "openldap", "OpenLDAP"

    # --- HTTPS / TLS ---
    https_enabled = models.BooleanField(
        "HTTPS activé", default=False,
        help_text="Redirige HTTP→HTTPS, active les cookies sécurisés et HSTS. "
        "La terminaison TLS est assurée par le reverse proxy (nginx).",
    )
    https_domain = models.CharField(
        "Domaine HTTPS", max_length=255, blank=True, default="",
        help_text="Domaine public servi en HTTPS (ex. agent.cyonima.dev).",
    )
    tls_cert_pem = models.TextField("Certificat TLS (PEM)", blank=True, default="")
    tls_key_pem = models.TextField("Clé privée TLS (PEM)", blank=True, default="")

    # --- LDAP / Active Directory ---
    ldap_enabled = models.BooleanField("LDAP activé", default=False)
    ldap_type = models.CharField(
        "Type d'annuaire", max_length=16,
        choices=LdapType.choices, default=LdapType.AD,
    )
    ldap_server_uri = models.CharField(
        "URI du serveur", max_length=255, blank=True, default="",
        help_text="Ex. ldap://dc.ad.example.com:389 ou ldaps://… (LDAPS avec TLS).",
    )
    ldap_bind_dn = models.CharField(
        "DN de liaison (service account)", max_length=255, blank=True, default="",
    )
    ldap_bind_password = models.CharField(
        "Mot de passe de liaison", max_length=255, blank=True, default="",
    )
    ldap_base_dn = models.CharField(
        "DN de base", max_length=255, blank=True, default="",
        help_text="Base de recherche des utilisateurs (ex. dc=ad,dc=example,dc=com).",
    )
    ldap_login_attribute = models.CharField(
        "Attribut de connexion", max_length=64, default="sAMAccountName",
        help_text="Attribut contenant l'identifiant saisi en bas de page : "
        "sAMAccountName (AD), uid (OpenLDAP) ou mail.",
    )
    ldap_user_filter = models.CharField(
        "Filtre utilisateur", max_length=255, blank=True, default="",
        help_text="Filtre de recherche LDAP, %(user)s est remplacé par "
        "l'identifiant. Laissé vide : cet attribut est dérivé de "
        "« Attribut de connexion ».",
    )
    ldap_email_domain = models.CharField(
        "Domaine email de repli", max_length=255, blank=True, default="",
        help_text="Si l'annuaire ne fournit pas d'email (ex. samaccountname), "
        "les comptes reçoivent <identifiant>@<ce domaine>.",
    )
    ldap_start_tls = models.BooleanField(
        "StartTLS", default=True,
        help_text="Active StartTLS sur la liaison (ldap://). Recommandé.",
    )
    ldap_user_attr = models.CharField(
        "Attribut nom complet", max_length=64, default="displayName",
        help_text="Attribut LDAP du nom complet (displayName ou cn).",
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuration système"
        verbose_name_plural = "Configuration système"

    @classmethod
    def get(cls) -> "SystemConfig":
        """Retourne le singleton (pk=1), créé au premier accès."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    # ------------------------------------------------------------------ HTTPS
    @property
    def is_https_ready(self) -> bool:
        return bool(self.tls_cert_pem and self.tls_key_pem)

    # ------------------------------------------------------------------- LDAP
    @property
    def ldap_identifier(self) -> str:
        return (self.ldap_login_attribute or "sAMAccountName").strip()

    @property
    def ldap_search_filter(self) -> str:
        if self.ldap_user_filter.strip():
            return self.ldap_user_filter.strip()
        return f"({self.ldap_identifier}=%(user)s)"

    def ldap_user_exists_locally(self, email: str) -> bool:
        User = get_user_model()
        return User.objects.filter(email__iexact=email).exists()