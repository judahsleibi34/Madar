# CSRF secret remediation

A new dedicated cryptographically generated `CSRF_SECRET` was provisioned in the protected production environment. It is not derived from or reused as the Supabase service credential or general application secret.

- The previous environment file was preserved under the protected Madar config-backup directory.
- The environment file remains owned by `madar:madar` with mode `0600`.
- Missing and short values fail closed in production tests.
- The final validator passed without displaying the value.

Changing CSRF signing material invalidates outstanding CSRF tokens, so a browser may need to fetch a new token. It does not rotate access/refresh tokens or the provider credential.
