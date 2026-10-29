"""One-time authorization interlock for privileged control-plane upgrades."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import pwd
import re
import time
from pathlib import Path


UPGRADE_INTERLOCK = Path("/run/madar/control-plane-upgrade/in-progress.json")
PRODUCTION_CONTROL_ROOT = Path("/opt/madar/control-plane/deployment")
PRODUCTION_MUTATION_USER = "madar"
RELEASE_OPERATOR_POLICY = Path('/etc/madar/release-operator-policy.json')
RELEASE_OPERATOR_KEY = Path('/etc/madar/release-operator-auth.key')


def authenticate_release_operator(token,*,environment_id,database_system_identifier,controller_sha,business_auth_key_sha256):
    """Independent infrastructure identity, NOT an approval or write grant.

    The existing root issuer consumes this observation only after technical
    admission. Tenant role/user metadata is never infrastructure authority.
    The auth realm must have a different signing key from the business app;
    its service-role credential therefore cannot impersonate an operator.
    """
    import base64
    import stat
    import uuid
    from urllib.parse import urlsplit
    from urllib.request import Request,build_opener,ProxyHandler,HTTPRedirectHandler
    from deployment.lib.migration_inventory import strict_json
    if os.geteuid()!=0:raise RuntimeError('release_operator_root_reader_required')
    def private(path,limit):
        for parent in path.parents:
            st=parent.lstat()
            if parent.is_symlink() or st.st_uid!=0 or st.st_mode&0o022:
                raise RuntimeError('release_operator_configuration_unprotected')
        fd=os.open(path,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW|os.O_NONBLOCK)
        with os.fdopen(fd,'rb') as stream:
            st=os.fstat(stream.fileno())
            if not stat.S_ISREG(st.st_mode) or st.st_uid!=0 or st.st_mode&0o077 or st.st_nlink!=1 or not 0<st.st_size<=limit:
                raise RuntimeError('release_operator_configuration_unprotected')
            value=stream.read(limit+1)
        if len(value)>limit:raise RuntimeError('release_operator_configuration_size')
        return value
    raw=private(RELEASE_OPERATOR_POLICY,32768);policy=strict_json(raw);key=private(RELEASE_OPERATOR_KEY,4096)
    fields={'version','repository','environment_id','database_system_identifier','controller_sha',
        'operator_auth_ids','issuer','audience','auth_user_url','auth_service','key_sha256',
        'valid_until','max_token_age_seconds','max_mfa_age_seconds'}
    if (not isinstance(policy,dict) or set(policy)!=fields or type(policy['version']) is not int or policy['version']!=1
            or policy['repository']!='judahsleibi34/Madar'
            or policy['environment_id']!=environment_id or policy['database_system_identifier']!=database_system_identifier
            or policy['controller_sha']!=controller_sha
            or not re.fullmatch('[a-zA-Z0-9_-]{1,128}',str(environment_id))
            or not re.fullmatch('[1-9][0-9]{0,31}',str(database_system_identifier))
            or not re.fullmatch('[a-f0-9]{40}',str(controller_sha))
            or not 32<=len(key)<=4096 or hashlib.sha256(key).hexdigest()!=policy['key_sha256']
            or not re.fullmatch('[a-f0-9]{64}',str(business_auth_key_sha256))
            or hmac.compare_digest(policy['key_sha256'],business_auth_key_sha256)
            or not isinstance(policy['operator_auth_ids'],list) or not 1<=len(policy['operator_auth_ids'])<=128
            or any(not isinstance(v,str) for v in policy['operator_auth_ids'])
            or len(set(policy['operator_auth_ids']))!=len(policy['operator_auth_ids'])):
        raise RuntimeError('release_operator_policy_invalid_or_business_realm')
    try:
        if any(str(uuid.UUID(v))!=v for v in policy['operator_auth_ids']):raise ValueError()
    except (ValueError,TypeError,AttributeError):raise RuntimeError('release_operator_identity_policy_invalid') from None
    now=int(time.time())
    if (type(policy['valid_until']) is not int or policy['valid_until']<=now
            or any(type(policy[k]) is not int or not 0<policy[k]<=maximum for k,maximum in
                   (('max_token_age_seconds',900),('max_mfa_age_seconds',300)))):
        raise RuntimeError('release_operator_policy_expired_or_unbounded')
    if not isinstance(token,str) or not 0<len(token)<=16384:raise RuntimeError('release_operator_credential_invalid')
    def decode(part):
        if not re.fullmatch('[a-zA-Z0-9_-]+',part):raise ValueError()
        body=base64.urlsafe_b64decode(part+'='*(-len(part)%4))
        if base64.urlsafe_b64encode(body).decode().rstrip('=')!=part:raise ValueError()
        return body
    try:
        header,body,signature=token.split('.')
        expected=hmac.new(key,(header+'.'+body).encode(),hashlib.sha256).digest()
        if not hmac.compare_digest(decode(signature),expected):raise ValueError()
        head=strict_json(decode(header));claims=strict_json(decode(body))
        if not isinstance(head,dict) or head.get('alg')!='HS256' or head.get('typ')!='JWT' or set(head)-{'alg','typ','kid'}:raise ValueError()
        if (not isinstance(claims,dict) or claims.get('iss')!=policy['issuer'] or claims.get('aud')!=policy['audience']
                or claims.get('role')!='authenticated' or claims.get('aal')!='aal2'
                or claims.get('sub') not in policy['operator_auth_ids']
                or any(type(claims.get(k)) is not int for k in ('iat','exp'))
                or not claims['iat']<=now<claims['exp'] or now-claims['iat']>policy['max_token_age_seconds']
                or ('nbf' in claims and (type(claims['nbf']) is not int or claims['nbf']>now))
                or not isinstance(claims.get('amr'),list) or len(claims['amr'])>16):raise ValueError()
        mfa=[item['timestamp'] for item in claims['amr'] if isinstance(item,dict) and item.get('method')=='totp'
             and type(item.get('timestamp')) is int and 0<=now-item['timestamp']<=policy['max_mfa_age_seconds']]
        if not mfa:raise ValueError()
        session=claims.get('session_id')
        if not isinstance(session,str) or str(uuid.UUID(session))!=session:raise ValueError()
    except (ValueError,KeyError,TypeError,AttributeError):raise RuntimeError('release_operator_identity_or_mfa_refused') from None
    try:
        uri=urlsplit(policy['auth_user_url'])
        if (uri.username or uri.password or uri.query or uri.fragment or not uri.hostname
                or uri.path not in {'/user','/auth/v1/user'}):raise ValueError()
        if uri.scheme=='https':
            if policy['auth_service'] is not None or uri.port not in {None,443}:raise ValueError()
        elif uri.scheme=='http':
            from deployment.lib.isolated_release_environment import observe,REALM_LABEL
            from deployment.lib.completed_normal_resources import measured_spec
            from deployment.lib.isolated_release_environment import run
            scope=observe();service=policy['auth_service']
            if (scope['database_system_identifier']!=database_system_identifier
                    or environment_id!='isolated-'+scope['realm_id'] or not isinstance(service,dict)
                    or set(service)!={'id','image','spec_sha256'} or not re.fullmatch('[a-f0-9]{64}',str(service['id']))):raise ValueError()
            rows=json.loads(run(['/usr/bin/docker','inspect',service['id']]))
            if (len(rows)!=1 or rows[0]['Id']!=service['id'] or rows[0]['Image']!=service['image']
                    or measured_spec(rows[0])!=service['spec_sha256'] or not rows[0]['State']['Running']
                    or rows[0]['Config'].get('Labels',{}).get(REALM_LABEL)!=scope['realm_id']
                    or uri.port!=9999 or uri.hostname not in {v['IPAddress'] for v in rows[0]['NetworkSettings']['Networks'].values()}):raise ValueError()
        else:raise ValueError()
    except (ValueError,KeyError,TypeError,AttributeError):raise RuntimeError('release_operator_provider_scope_invalid') from None
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    try:
        opener=build_opener(ProxyHandler({}),NoRedirect())
        with opener.open(Request(policy['auth_user_url'],headers={'Authorization':'Bearer '+token}),timeout=5) as response:
            if response.status!=200:raise ValueError()
            body=response.read(65537)
            if len(body)>65536:raise ValueError()
            profile=strict_json(body)
            if (not isinstance(profile,dict) or profile.get('id')!=claims['sub'] or profile.get('banned_until')
                    or profile.get('is_anonymous') is True or not isinstance(profile.get('factors'),list)
                    or not any(isinstance(f,dict) and f.get('factor_type')=='totp' and f.get('status')=='verified'
                               for f in profile['factors'])):
                raise ValueError()
    except Exception:raise RuntimeError('release_operator_current_identity_unverified') from None
    return {'operator_auth_id':claims['sub'],'aal':'aal2','mfa_authenticated_at':max(mfa),
        'authenticated_at':now,'policy_sha256':hashlib.sha256(raw).hexdigest(),
        'verification_key_sha256':policy['key_sha256'],'session_id_sha256':hashlib.sha256(session.encode()).hexdigest()}


def require_production_mutation_identity(
    script: Path,
    *,
    installed_root: Path = PRODUCTION_CONTROL_ROOT,
    user: str = PRODUCTION_MUTATION_USER,
) -> None:
    """Fail closed when installed production mutators run as another identity.

    Repository, staging, and test copies are intentionally unaffected. Only
    executables beneath the installed production control-plane root enforce
    the canonical deployment UID/GID.
    """

    resolved_script = Path(script).resolve()
    resolved_root = Path(installed_root).resolve()

    if not resolved_script.is_relative_to(resolved_root):
        return

    try:
        identity = pwd.getpwnam(user)
    except KeyError as error:
        raise RuntimeError(
            "production_mutation_identity_invalid"
        ) from error

    if (
        os.geteuid() != identity.pw_uid
        or os.getegid() != identity.pw_gid
    ):
        raise RuntimeError("production_mutation_identity_invalid")


def require_upgrade_authorization(
    sha: str | None, *, interlock: Path = UPGRADE_INTERLOCK,
    required_operation: str | None = None,
    required_schema: int | None = None,
    require_rehearsal: bool = False,
    required_context_digest: str | None = None,
) -> None:
    """Reject deployment races while a root upgrader owns orchestration.

    A transient systemd unit exposes a root-sourced credential only inside the
    unit credential boundary. The public interlock contains only a SHA and a
    one-way digest, never the bearer token.
    """

    if not interlock.exists() and required_operation is not None:
        raise RuntimeError("control_plane_recovery_authorization_required")
    if not interlock.exists():
        return
    if interlock.is_symlink():
        raise RuntimeError("control_plane_upgrade_interlock_invalid")
    interlock_stat = interlock.stat()
    if interlock_stat.st_uid != 0 or interlock_stat.st_mode & 0o022:
        raise RuntimeError("control_plane_upgrade_interlock_invalid")
    try:
        state = json.loads(interlock.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise RuntimeError("control_plane_upgrade_interlock_invalid") from error
    if state.get("operation") == "provider402-signin" and required_operation != "provider402-signin":
        raise RuntimeError("provider_recovery_operation_not_authorized")
    credential_root = os.getenv("CREDENTIALS_DIRECTORY", "").strip()
    credential = (
        Path(credential_root) / "madar-control-plane-upgrade"
        if credential_root.startswith("/")
        else None
    )
    try:
        if credential is None or not credential.is_file() or credential.is_symlink():
            raise OSError
        authorization = json.loads(credential.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise RuntimeError("control_plane_upgrade_exclusive_interlock") from error
    authorized_sha = str(authorization.get("approved_sha") or "").lower()
    token = str(authorization.get("token") or "")
    expected_digest = str(state.get("authorization_sha256") or "")
    actual_digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    if (
        (sha is not None and state.get("approved_sha") != sha)
        or authorized_sha != state.get("approved_sha")
        or not token
        or not re.fullmatch(r"[0-9a-f]{64}", expected_digest)
        or not hmac.compare_digest(actual_digest, expected_digest)
        or (required_operation is not None and state.get("operation") != required_operation)
        or (required_operation is not None and authorization.get("operation") != required_operation)
        or (required_schema is not None and state.get("schema") != required_schema)
        or (required_schema is not None and authorization.get("schema") != required_schema)
        or (required_context_digest is not None and (
            not re.fullmatch(r"[0-9a-f]{64}", required_context_digest)
            or state.get("context_sha256") != required_context_digest
            or authorization.get("context_sha256") != required_context_digest
        ))
        or (
            require_rehearsal
            and (
                not re.fullmatch(r"[0-9a-f]{64}", str(state.get("rehearsal_sha256") or ""))
                or authorization.get("rehearsal_sha256") != state.get("rehearsal_sha256")
            )
        )
    ):
        raise RuntimeError("control_plane_upgrade_exclusive_interlock")
