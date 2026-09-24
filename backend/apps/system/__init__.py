"""Application `system` : configuration dynamique de l'app (HTTPS, LDAP/AD).

Contrairement aux réglages via `.env` (lus au démarrage), `SystemConfig`
permet à un administrateur de modifier certains comportements **à chaud** depuis
l'interface d'administration :
- activer le HTTPS (redirection + cookies sécurisés + HSTS) et gérer le
  certificat TLS ;
- connecter un annuaire **Active Directory / OpenLDAP** pour l'authentification.
"""