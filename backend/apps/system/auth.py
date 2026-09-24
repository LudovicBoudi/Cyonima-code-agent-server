"""Backend d'authentification LDAP / Active Directory.

Lis la configuration **en base** (`SystemConfig`) à chaque tentative : les
réglages faits depuis l'interface d'administration sont donc appliqués sans
redémarrer le serveur.

Flux : liaison service → recherche de l'utilisateur → vérification du mot de
passe → création (get_or_create) du compte local Django (login par email) et
mise à jour du nom complet.
"""
import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

from .models import SystemConfig
from .services import authenticate_ldap, derive_email, display_fullname

logger = logging.getLogger(__name__)


class LdapBackend(ModelBackend):
    """Authentifie un utilisateur contre un annuaire AD/OpenLDAP. Local sinon."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None

        config = SystemConfig.get()
        if not config.ldap_enabled:
            return None

        ok, message, attrs = authenticate_ldap(config, username, password)
        if not ok:
            logger.info("Login LDAP refusé pour %s (%s)", username, message)
            return None

        try:
            email = derive_email(config, username, attrs)
        except ValueError as exc:
            logger.warning("Login LDAP %s sans email: %s", username, exc)
            return None

        User = get_user_model()
        user, created = User.objects.get_or_create(
            email__iexact=email,
            defaults={"email": email},
        )
        if created:
            logger.info("Compte local créé pour %s (via %s)", email, config.ldap_type)
        name = display_fullname(config, attrs)
        if name and user.name != name:
            user.name = name
            user.save(update_fields=["name"])
        return user

    def get_user(self, user_id):
        User = get_user_model()
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

    def user_can_authenticate(self, user):
        # Un compte désactivé localement ne peut pas se connecter, même valide LDAP.
        return super().user_can_authenticate(user)