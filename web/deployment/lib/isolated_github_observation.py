"""Read-only GitHub observations for an egress-fenced disposable KVM guest.

This is an evidence transport for the existing artifact/admission validators.
The existing independent test observer key stays on the parent host. No GitHub
token enters the guest and no response issues release or migration authority.
Without this explicit root policy, callers use their original direct API path.
"""
import base64,hashlib,os,re,subprocess,time,uuid
from pathlib import Path
from .migration_inventory import canonical,digest,strict_json
from .provider_recovery_runtime import protected

POLICY=Path('/etc/madar/isolated-github-observation.json')
ROOT=Path('/var/lib/madar-control-plane/github-observations')
REPOSITORY='judahsleibi34/Madar'
MAX_BYTES=2*1024**2
SCOPE=('environment_id','guest_uuid','machine_id','root_filesystem_uuid','database_system_identifier',
       'controller_sha','controller_tree_sha256')


def endpoint_allowed(endpoint):
    if not isinstance(endpoint,str):return False
    prefix='repos/'+REPOSITORY+'/'
    if not endpoint.startswith(prefix):return False
    relative=endpoint[len(prefix):]
    return bool(re.fullmatch(r'commits/[a-f0-9]{40}',relative)
        or re.fullmatch(r'actions/(artifacts|runs)/[1-9][0-9]{0,19}',relative)
        or re.fullmatch(r'actions/workflows/(backend-check|frontend-check|migration-safety|schema148-artifacts|full-provider-staging)\.yml/runs\?head_sha=[a-f0-9]{40}&per_page=100',relative))


def validate_policy(value,*,now):
    fields={'version','kind',*SCOPE,'test_public_key_sha256','endpoints','expires_at','denied_database_identifiers'}
    if (not isinstance(value,dict) or set(value)!=fields or type(value['version']) is not int or value['version']!=1
            or value['kind']!='isolated-parent-github-observation'
            or any(not isinstance(value[k],str) for k in (*SCOPE,'test_public_key_sha256'))
            or not re.fullmatch('isolated-[a-f0-9-]{36}',str(value['environment_id']))
            or any(not re.fullmatch('[a-f0-9]{40}',str(value[k])) for k in ('controller_sha',))
            or any(not re.fullmatch('[a-f0-9]{64}',str(value[k])) for k in ('controller_tree_sha256','test_public_key_sha256'))
            or not re.fullmatch('[a-f0-9]{32}',str(value['machine_id']))
            or not re.fullmatch('[1-9][0-9]{0,31}',str(value['database_system_identifier']))
            or not isinstance(value['denied_database_identifiers'],list) or not 1<=len(value['denied_database_identifiers'])<=64
            or any(not isinstance(v,str) or not re.fullmatch('[1-9][0-9]{0,31}',v) for v in value['denied_database_identifiers'])
            or value['database_system_identifier'] in value['denied_database_identifiers']
            or type(value['expires_at']) is not int or not now<value['expires_at']<=now+10800
            or not isinstance(value['endpoints'],list) or not 1<=len(value['endpoints'])<=32
            or any(not endpoint_allowed(e) for e in value['endpoints'])
            or len(set(value['endpoints']))!=len(value['endpoints'])):
        raise RuntimeError('isolated_github_policy_invalid')
    try:
        for key in ('guest_uuid','root_filesystem_uuid'):
            if str(uuid.UUID(value[key]))!=value[key]:raise ValueError()
        if str(uuid.UUID(value['environment_id'].removeprefix('isolated-'))) != value['environment_id'].removeprefix('isolated-'):raise ValueError()
    except (ValueError,TypeError,AttributeError):raise RuntimeError('isolated_github_policy_invalid') from None
    return value


def policy(operations):
    if os.geteuid()!=0:raise RuntimeError('isolated_github_root_reader_required')
    raw=protected(POLICY,private=True).read_bytes()
    if not 0<len(raw)<=32768:raise RuntimeError('isolated_github_policy_size')
    value=validate_policy(strict_json(raw),now=int(time.time()))
    from .automatic_release_admission import TEST_PUBLIC_KEY
    key=protected(TEST_PUBLIC_KEY,private=True).read_bytes()
    from .isolated_release_environment import observe_host,observe_effect_fence
    from .active_recovery_inputs import controller_tree_digest
    host=observe_host()
    if (host['version']!=2 or value['environment_id']!='isolated-'+host['realm_id']
            or any(value[k]!=host[k] for k in ('guest_uuid','machine_id','root_filesystem_uuid','database_system_identifier'))
            or len(key)!=32 or hashlib.sha256(key).hexdigest()!=value['test_public_key_sha256']
            or operations.installed_sha()!=value['controller_sha'] or controller_tree_digest()!=value['controller_tree_sha256']):
        raise RuntimeError('isolated_github_guest_or_observer_changed')
    observe_effect_fence(execution=True)
    return value,key


def validate_request(request,p,*,now):
    fields={'version','kind','policy_sha256',*SCOPE,'nonce','endpoint','created_at','expires_at'}
    if (not isinstance(request,dict) or set(request)!=fields or type(request['version']) is not int or request['version']!=1
            or request['kind']!='isolated-read-only-github-query' or request['policy_sha256']!=digest(p)
            or any(request[k]!=p[k] for k in SCOPE) or request['endpoint'] not in p['endpoints']
            or any(type(request[k]) is not int for k in ('created_at','expires_at'))
            or not 0<=now-request['created_at']<=60
            or not now<request['expires_at']<=min(p['expires_at'],request['created_at']+60)):
        raise RuntimeError('isolated_github_request_scope_or_freshness')
    try:
        if str(uuid.UUID(request['nonce']))!=request['nonce']:raise ValueError()
    except (ValueError,TypeError,AttributeError):raise RuntimeError('isolated_github_request_nonce') from None
    return request


class ParentObservationError(RuntimeError):
    """Allowlisted diagnostic only; never retain raw API output or credentials."""
    def __init__(self,classification,attempts,endpoint,status=None):
        self.diagnostic={'classification':classification,'attempts':attempts,
            'endpoint_sha256':hashlib.sha256(endpoint.encode()).hexdigest(),'http_status':status}
        super().__init__('isolated_github_parent_api_failed:'+classification+
            ':attempts='+str(attempts)+':http='+str(status))


def parent_get(request,p):
    # One original nonce/expiry, fixed host and GET only. Monotonic bounds local
    # elapsed time; wall-clock expiry is independently checked at each attempt.
    deadline=time.monotonic()+min(55,max(0,min(request['expires_at'],p['expires_at'])-time.time()-2))
    for attempt in range(1,4):
        now=int(time.time());validate_policy(p,now=now);validate_request(request,p,now=now)
        remaining=min(deadline-time.monotonic(),min(request['expires_at'],p['expires_at'])-time.time()-2)
        if remaining<=0:raise ParentObservationError('deadline',attempt-1,request['endpoint'])
        status=None
        try:
            result=subprocess.run(['/usr/bin/gh','api','--hostname','github.com','--method','GET',request['endpoint']],
                capture_output=True,timeout=min(15,remaining),
                env={'PATH':os.defpath,'HOME':os.path.expanduser('~'),'LANG':'C.UTF-8'})
            if result.returncode==0:return result
            # Classify only gh's bounded stderr; never expose it in diagnostics.
            error=getattr(result,'stderr',b'')[:8192].decode('utf-8',errors='replace')
            match=re.search(r'\(HTTP ([1-5][0-9]{2})\)',error)
            status=int(match[1]) if match else None
            transient=status in (429,500,502,503,504)
            transport=not status and any(x in error.lower() for x in
                ('connection reset by peer','connection timed out','temporary failure in name resolution',
                 'tls handshake timeout','unexpected eof','i/o timeout'))
            classification='transient_http' if transient else 'transport' if transport else 'permanent_or_unknown'
        except subprocess.TimeoutExpired:
            classification='transport_timeout';transient=True;transport=False
        if not (transient or transport) or attempt==3:
            raise ParentObservationError(classification,attempt,request['endpoint'],status)
        delay=attempt
        if min(deadline-time.monotonic(),min(request['expires_at'],p['expires_at'])-time.time()-2)<=delay:
            raise ParentObservationError('deadline',attempt,request['endpoint'],status)
        time.sleep(delay)


def observe_on_parent(request,p,private_key):
    """Parent supplies its independently pinned policy, not guest policy input.

    Always perform the real fixed-host GitHub GET. No caller-provided response,
    PASS field, URL, token or command is accepted. Signing this metadata cannot
    replace the existing source/CI/artifact/staging or release approval checks.
    """
    now=int(time.time());validate_policy(p,now=now);validate_request(request,p,now=now)
    from cryptography.hazmat.primitives import serialization
    public=private_key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    if hashlib.sha256(public).hexdigest()!=p['test_public_key_sha256']:
        raise RuntimeError('isolated_github_parent_key_changed')
    # A controlled environment prevents GH_HOST or an alternate credential
    # configuration from redirecting this query to another GitHub service.
    result=parent_get(request,p)
    if not 0<len(result.stdout)<=MAX_BYTES:raise RuntimeError('isolated_github_parent_api_size')
    value=strict_json(result.stdout)
    if not isinstance(value,dict):raise RuntimeError('isolated_github_parent_api_shape')
    observed=int(time.time());validate_policy(p,now=observed);validate_request(request,p,now=observed)
    payload={'version':1,'kind':'isolated-parent-github-response','request':request,'observed_at':observed,
        'response':value,'response_sha256':digest(value)}
    return {'payload':payload,'signature':base64.b64encode(private_key.sign(canonical(payload))).decode()}


def verify_response(packet,request,p,key,*,now):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    validate_policy(p,now=now);validate_request(request,p,now=now)
    if (not isinstance(packet,dict) or set(packet)!={'payload','signature'}
            or len(key)!=32 or hashlib.sha256(key).hexdigest()!=p['test_public_key_sha256']):
        raise RuntimeError('isolated_github_response_envelope')
    try:Ed25519PublicKey.from_public_bytes(key).verify(base64.b64decode(packet['signature'],validate=True),canonical(packet['payload']))
    except Exception:raise RuntimeError('isolated_github_response_signature') from None
    payload=packet['payload']
    if (not isinstance(payload,dict) or set(payload)!={'version','kind','request','observed_at','response','response_sha256'}
            or type(payload['version']) is not int or payload['version']!=1 or payload['kind']!='isolated-parent-github-response'
            or digest(payload['request'])!=digest(request) or type(payload['observed_at']) is not int
            or not request['created_at']<=payload['observed_at']<=now<request['expires_at']
            or not isinstance(payload['response'],dict) or digest(payload['response'])!=payload['response_sha256']):
        raise RuntimeError('isolated_github_response_scope_or_freshness')
    return payload['response']


def api(endpoint,*,operations=None,label='github_evidence',timeout=30):
    """Direct production observer unchanged; isolated transport explicitly pinned."""
    if not endpoint_allowed(endpoint):raise RuntimeError('release_github_endpoint_refused')
    if not POLICY.exists() and not POLICY.is_symlink():
        args=['/usr/sbin/runuser','-u','madar','--','/usr/bin/gh','api',endpoint]
        raw=(operations.command(label,args,timeout=timeout).stdout if operations is not None
            else subprocess.check_output(args,timeout=timeout))
        if isinstance(raw,str):raw=raw.encode()
        if not 0<len(raw)<=MAX_BYTES:raise RuntimeError('release_github_api_size')
        value=strict_json(raw)
        if not isinstance(value,dict):raise RuntimeError('release_github_api_shape')
        return value
    if operations is None:
        from .control_plane_upgrade import SystemOperations
        operations=SystemOperations()
    p,key=policy(operations)
    if endpoint not in p['endpoints']:raise RuntimeError('isolated_github_endpoint_not_enrolled')
    from .control_plane_upgrade import require_root_directory
    from .migration_executor import atomic_json
    require_root_directory(ROOT,create=True)
    if len(list(ROOT.glob('*.request.json')))+len(list(ROOT.glob('*.response.json')))>=64:
        raise RuntimeError('isolated_github_pending_budget')
    if len(list(ROOT.glob('*.audit.json')))>=512:raise RuntimeError('isolated_github_audit_budget')
    now=int(time.time());nonce=str(uuid.uuid4())
    request={'version':1,'kind':'isolated-read-only-github-query','policy_sha256':digest(p),
        **{k:p[k] for k in SCOPE},'nonce':nonce,'endpoint':endpoint,'created_at':now,'expires_at':min(now+60,p['expires_at'])}
    query=ROOT/(nonce+'.request.json');response=ROOT/(nonce+'.response.json')
    atomic_json(query,request,exclusive=True);deadline=time.monotonic()+60;status='FAILED';response_hash=None
    try:
        while time.monotonic()<deadline and int(time.time())<request['expires_at']:
            if response.exists() or response.is_symlink():
                raw=protected(response,private=True).read_bytes()
                if not 0<len(raw)<=MAX_BYTES+65536:raise RuntimeError('isolated_github_response_size')
                response_hash=hashlib.sha256(raw).hexdigest()
                result=verify_response(strict_json(raw),request,p,key,now=int(time.time()))
                if policy(operations)!=(p,key):raise RuntimeError('isolated_github_policy_changed_during_query')
                status='OBSERVED'
                return result
            time.sleep(0.25)
        raise RuntimeError('isolated_github_parent_observation_timeout')
    finally:
        atomic_json(ROOT/(nonce+'.audit.json'),{'request':request,'result':status,
            'response_packet_sha256':response_hash,'recorded_at':int(time.time()),'deployment_authority_issued':False},exclusive=True)
        # Only this nonce's authenticated files; stale/foreign entries are never
        # swept by age or used to authorize a later query.
        if canonical(strict_json(protected(query,private=True).read_bytes()))!=canonical(request):
            raise RuntimeError('isolated_github_query_changed')
        query.unlink()
        if response.exists() or response.is_symlink():
            protected(response,private=True);response.unlink()
