"""Services métier : HTTPS (certificat + nginx) et LDAP (test, liaison).

Isolés des vues pour être réutilisables (management commands, tests, shell).
"""
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from django.conf import settings

from .models import SystemConfig

logger = logging.getLogger(__name__)

TLS_DIR = Path(settings.BASE_DIR) / "data" / "tls"


def tls_dir() -> Path:
    TLS_DIR.mkdir(parents=True, exist_ok=True)
    return TLS_DIR


# ---------------------------------------------------------------------------
# HTTPS
# ---------------------------------------------------------------------------
def generate_self_signed(domain: str, days: int = 825) -> tuple[str, str]:
    """Génère un certificat auto-signé (RSA 2048) et sa clé privée (PEM).

    Returns: (cert_pem, key_pem)
    """
    if not domain:
        domain = "localhost"
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, domain)]
    )
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=days))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(domain)]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode()
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ).decode()
    return cert_pem, key_pem


def write_tls_files(config: SystemConfig) -> list[str]:
    """Écrit le certificat/clé PEM sur disque + un site nginx HTTPS prêt à
    l'emploi. Retourne une liste de messages explicatifs."""
    messages: list[str] = []
    if not config.is_https_ready:
        return ["Certificat absent : générez-en un (bouton « Générer auto-signé »)."]

    d = tls_dir()
    safe = config.https_domain.strip().replace("/", "_") or "server"
    cert_path = d / f"{safe}.crt"
    key_path = d / f"{safe}.key"
    cert_path.write_text(config.tls_cert_pem)
    key_path.write_text(config.tls_key_pem)
    _generate_nginx_site(d, safe)
    messages.append(f"Certificat écrit dans {cert_path}")
    messages.append(f"Site nginx prêt : {d / 'https-site.conf'}")
    return messages


def _generate_nginx_site(d: Path, base: str) -> None:
    content = f"""# Site HTTPS généré par l'application (SystemConfig).
# À monter dans le conteneur frontend : volume ${{BACKEND}}/data/tls:/etc/nginx/tls:ro
# puis copier ce fichier dans /etc/nginx/conf.d/ et exec nginx -s reload.
server {{
    listen 443 ssl;
    server_name {base};

    ssl_certificate     /etc/nginx/tls/{base}.crt;
    ssl_certificate_key /etc/nginx/tls/{base}.key;
    ssl_protocols TLSv1.2 TLSv1.3;

    root /usr/share/nginx/html;
    index index.html;

    location /api/  {{ proxy_pass http://backend:8000; proxy_set_header Host $host; proxy_set_header X-Real-IP $remote_addr; proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; proxy_set_header X-Forwarded-Proto $scheme; }}
    location /ws/   {{ proxy_pass http://backend:8000; proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade"; proxy_set_header X-Forwarded-Proto $scheme; }}
    location /admin/{{ proxy_pass http://backend:8000; proxy_set_header X-Forwarded-Proto $scheme; }}
    location /      {{ try_files $uri $uri/ /index.html; }}
}}

server {{
    listen 80;
    server_name {base};
    return 301 https://$host$request_uri;
}}
"""
    (d / "https-site.conf").write_text(content)


# ---------------------------------------------------------------------------
# LDAP
# ---------------------------------------------------------------------------
def derive_email(config: SystemConfig, username: str, attrs: dict | None) -> str:
    """Construit l'email local à partir des attributs LDAP ou d'un repli."""
    if attrs:
        for key in ("mail", "userPrincipalName", "email"):
            val = attrs.get(key) or ""
            if isinstance(val, list):
                val = val[0] if val else ""
            if val:
                return str(val).strip()
    if "@" in username:
        return username
    if config.ldap_email_domain:
        return f"{username}@{config.ldap_email_domain}".lower()
    raise ValueError(
        "Impossible de déterminer l'email du compte : aucun attribut mail et "
        "aucun domaine de repli configuré."
    )


def display_fullname(config: SystemConfig, attrs: dict | None) -> str:
    if not attrs:
        return ""
    for key in (config.ldap_user_attr, "displayName", "cn"):
        val = attrs.get(key)
        if isinstance(val, list):
            val = val[0] if val else None
        if val:
            return str(val)
    return ""


def _connect(uri: str, user: str = "", password: str = "", start_tls: bool = False):
    """Ouvre une connexion LDAP et exécute un bind. Retourne (conn, ok)."""
    import ldap3  # import tardif pour rater proprement si absent

    server = ldap3.Server(uri, get_info=ldap3.NONE, connect_timeout=10)
    conn = ldap3.Connection(
        server, user=user or None, password=password or None,
        receive_timeout=10, raise_exceptions=False,
    )
    try:
        if start_tls and uri.lower().startswith("ldap://"):
            if not conn.open():
                return conn, False
            conn.start_tls()
        ok = conn.bind()
        return conn, bool(ok)
    except Exception:  # noqa: BLE001
        return conn, False


def authenticate_ldap(config: SystemConfig, username: str, password: str) -> tuple[bool, str, dict | None]:
    """Liaison service → recherche utilisateur → vérification du mot de passe.

    Retourne (ok, message, attrs). Le mot de passe n'est jamais stocké ni
    journalisé.
    """
    uri = config.ldap_server_uri.strip()
    if not uri:
        return False, "URI du serveur LDAP non configurée.", None
    user = (username or "").strip()
    if not user or not password:
        return False, "Identifiants incomplets.", None

    try:
        import ldap3
    except ImportError:  # pragma: no cover
        logger.error("ldap3 n'est pas installé")
        return False, "Librairie LDAP indisponible", None

    service_conn, bound = _connect(
        uri,
        user=config.ldap_bind_dn.strip() or "",
        password=config.ldap_bind_password,
        start_tls=config.ldap_start_tls,
    )
    if not bound:
        return False, "Liaison service impossible (DN de liaison ?).", None

    try:
        search_filter = config.ldap_search_filter.strip() or (
            f"({config.ldap_login_attribute.strip() or 'sAMAccountName'}={user})"
        )
        found = service_conn.search(
            search_base=config.ldap_base_dn.strip() or "",
            search_filter=search_filter,
            attributes=ldap3.ALL_ATTRIBUTES,
            search_scope=ldap3.SUBTREE,
        )
        if not found or not service_conn.entries:
            return False, "Identifiants incorrects.", None

        entry = service_conn.entries[0]
        user_dn = str(entry.entry_dn)
        attrs = {str(a): entry[a].value for a in entry.entry_attributes}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Recherche LDAP échouée (%s): %s", uri, exc)
        return False, "Serveur LDAP injoignable.", None
    finally:
        try:
            service_conn.unbind()
        except Exception:  # noqa: BLE001
            pass

    # Vérifier le mot de passe de l'utilisateur sur son propre DN.
    user_conn, ok = _connect(uri, user=user_dn, password=password, start_tls=config.ldap_start_tls)
    if not ok:
        return False, "Identifiants incorrects.", None
    try:
        return True, "Authentification LDAP réussie.", attrs
    finally:
        try:
            user_conn.unbind()
        except Exception:  # noqa: BLE001
            pass


def test_ldap_connection(config: SystemConfig) -> dict:
    """Teste la connexion au serveur LDAP (liaison service, sans user)."""
    uri = config.ldap_server_uri.strip()
    if not uri:
        return {"ok": False, "message": "URI du serveur LDAP non configurée."}
    try:
        import ldap3  # noqa: F401
    except ImportError:  # pragma: no cover
        return {"ok": False, "message": "ldap3 non installé sur le serveur."}

    conn, ok = _connect(
        uri,
        user=config.ldap_bind_dn.strip() or "",
        password=config.ldap_bind_password,
        start_tls=config.ldap_start_tls,
    )
    if not ok:
        return {"ok": False, "message": "Liaison LDAP refusée (DN/password ?)."}
    try:
        if config.ldap_base_dn.strip():
            conn.search(
                search_base=config.ldap_base_dn.strip(),
                search_filter="(objectClass=*)",
                attributes=["1.1"],
                size_limit=1,
                search_scope=ldap3.SUBTREE,
            )
        return {"ok": True, "message": "Connexion au serveur LDAP réussie."}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "message": f"Erreur LDAP : {exc}"}
    finally:
        try:
            conn.unbind()
        except Exception:  # noqa: BLE001
            pass