"""Read-only native consumer scope checks. No service stop or credential output."""
import base64
import hashlib
import hmac
import ipaddress
import json
import re
from urllib.parse import urlsplit
from urllib.error import HTTPError
from urllib.request import Request,build_opener,ProxyHandler,HTTPRedirectHandler


def environment(row):
    result={}
    for entry in row.get('Config',{}).get('Env',[]) or []:
        key,separator,value=entry.partition('=')
        if not separator or key in result:raise RuntimeError('schema148_consumer_environment_ambiguous')
        result[key]=value
    return result


def foreign_service_credential(token,target_secret):
    """Different HS256 signing authority, never merely a different JWT string.

    Expired target-signed tokens are NOT unrelated: their authority can renew.
    Unknown signing schemes fail closed. No production token is generated.
    """
    try:
        if not isinstance(token,str):raise ValueError()
        header,payload,signature=token.split('.')
        decode=lambda value:base64.urlsafe_b64decode(value+'='*(-len(value)%4))
        decoded_header,decoded_payload=json.loads(decode(header)),json.loads(decode(payload))
        if not isinstance(decoded_header,dict) or not isinstance(decoded_payload,dict) or decoded_header.get('alg')!='HS256' or decoded_payload.get('role')!='service_role':
            raise ValueError()
        supplied=decode(signature)
        if len(supplied)!=32 or not isinstance(target_secret,str) or len(target_secret)<32 or target_secret.lstrip().startswith(('{','[','@')):
            raise ValueError()
        expected=hmac.new(target_secret.encode(),(header+'.'+payload).encode(),hashlib.sha256).digest()
        return not hmac.compare_digest(supplied,expected)
    except (ValueError,TypeError,KeyError):
        raise RuntimeError('schema148_consumer_credential_scope_unverified') from None


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def authorization_probe(url,token):
    # Bounded read on the measured native PostgREST; no RPC, credentials in
    # argv, proxy inheritance, redirects, raw response or token logging.
    try:
        opener=build_opener(ProxyHandler({}),NoRedirect())
        try:response=opener.open(Request(url,headers={'Authorization':'Bearer '+token}),timeout=3)
        except HTTPError as error:response=error
        with response:return response.status,json.loads(response.read(65536))
    except Exception:raise RuntimeError('schema148_native_authorization_probe_unavailable') from None


def unrelated_consumers(rows,contract,bindings,*,candidate_ids,target_rest_binding):
    if not isinstance(bindings,dict):raise RuntimeError('schema148_unrelated_binding_invalid')
    if not bindings:return set()
    by_id={row['Id']:row for row in rows}
    native=by_id.get(contract['database']['container_id'])
    if native is None or native['Image']!=contract['database']['image']:
        raise RuntimeError('schema148_native_identity_changed')
    network=contract['database']['network_id']
    aliases={name for entry in native['NetworkSettings']['Networks'].values() for name in (entry.get('Aliases') or [])}
    aliases.update({native.get('Name','').lstrip('/'),native.get('Config',{}).get('Hostname','')})
    candidates=[]
    for row in rows:
        values=environment(row)
        if 'PGRST_DB_URI' not in values:continue
        location=urlsplit(values['PGRST_DB_URI'])
        networks=row.get('NetworkSettings',{}).get('Networks',{}).values()
        if location.hostname in aliases and location.path=='/postgres' and location.port in (None,5432) and any(entry.get('NetworkID')==network for entry in networks):
            if values.get('PGRST_JWT_SECRET_IS_BASE64','false').lower()!='false':
                raise RuntimeError('schema148_target_signing_scheme_unverified')
            candidates.append((row,values))
    if len(candidates)!=1:raise RuntimeError('schema148_target_signing_authority_ambiguous')
    rest,rest_env=candidates[0]
    from deployment.lib.completed_normal_resources import measured_spec_matches
    if (not isinstance(target_rest_binding,dict) or set(target_rest_binding)!={'id','image','spec_sha256'}
            or rest['Id']!=target_rest_binding['id'] or rest.get('Name')!='/supabase-rest'
            or rest.get('Image')!=target_rest_binding['image']
            or not rest.get('State',{}).get('Running')
            or not measured_spec_matches(rest,target_rest_binding['spec_sha256'])):
        raise RuntimeError('schema148_target_rest_identity_changed')
    target_secret=rest_env.get('PGRST_JWT_SECRET')
    addresses={entry.get('IPAddress') for entry in rest['NetworkSettings']['Networks'].values() if entry.get('NetworkID')==network}
    if len(addresses)!=1:raise RuntimeError('schema148_native_authorization_address_ambiguous')
    address=addresses.pop()
    try:
        if not ipaddress.ip_address(address).is_private:raise ValueError()
        port=int(rest_env.get('PGRST_SERVER_PORT','3000'))
        if not 0<port<65536:raise ValueError()
    except (ValueError,TypeError):raise RuntimeError('schema148_native_authorization_address_invalid') from None
    target_tokens={environment(by_id[identifier]).get('SUPABASE_SERVICE_KEY') for identifier in candidate_ids if identifier in by_id}
    if len(target_tokens)!=1:raise RuntimeError('schema148_target_credential_ambiguous')
    target_token=target_tokens.pop()
    if foreign_service_credential(target_token,target_secret):raise RuntimeError('schema148_target_credential_unverified')
    url=f'http://{address}:{port}/application_schema_state?select=schema_version&contract_key=eq.core&limit=1'
    status,body=authorization_probe(url,target_token)
    if status!=200 or not isinstance(body,list) or len(body)!=1 or type(body[0].get('schema_version')) is not int or body[0]['schema_version'] not in (146,147,148):
        raise RuntimeError('schema148_native_authorization_positive_control_failed')
    from deployment.lib.completed_normal_resources import measured_spec_matches
    result=set()
    for identifier,binding in bindings.items():
        row=by_id.get(identifier)
        if (not re.fullmatch('[0-9a-f]{64}',identifier) or not isinstance(binding,dict)
                or set(binding)!={'image','spec_sha256'} or row is None or row['Image']!=binding['image']
                or not re.fullmatch('[0-9a-f]{64}',str(binding['spec_sha256']))
                or not measured_spec_matches(row,binding['spec_sha256'])):
            raise RuntimeError('schema148_unrelated_identity_changed')
        values=environment(row)
        # Only the reviewed native SDK credential path can be excluded this way.
        # Direct DB credentials require separately reviewed scope evidence.
        if any(values.get(key) for key in ('DATABASE_URL','SUPABASE_DB_URL','PGPASSWORD','SUPABASE_SERVICE_ROLE_KEY','JWT_SECRET','SUPABASE_JWT_SECRET','GOTRUE_JWT_SECRET')):
            raise RuntimeError('schema148_unrelated_direct_credentials_unverified')
        if not foreign_service_credential(values.get('SUPABASE_SERVICE_KEY',''),target_secret):
            raise RuntimeError('schema148_unrelated_credential_can_target_database')
        status,body=authorization_probe(url,values['SUPABASE_SERVICE_KEY'])
        if status!=401 or not isinstance(body,dict) or body.get('code')!='PGRST301':
            raise RuntimeError('schema148_unrelated_live_authorization_unverified')
        result.add(identifier)
    return result


def host_processes(runtime,allowed_container_ids,*,required_pids):
    """Catch host/manual or docker-exec native workers omitted by Config.Cmd.

    Inspect only process identity/cgroups. Command contents and credentials are
    never returned as evidence, logs or metric labels.
    """
    observed=0;seen=set()
    for line in runtime.command(['ps','-eo','pid=,args=']).splitlines():
        fields=line.strip().split(None,1)
        if len(fields)!=2 or not re.search(r'(?:^|[\s/]|workers[./])notification_worker(?:\.py|\b)',fields[1]):continue
        if not fields[0].isdigit():raise RuntimeError('schema148_host_consumer_ambiguous')
        try:group=runtime.command(['cat','/proc/'+fields[0]+'/cgroup'])
        except Exception:raise RuntimeError('schema148_host_consumer_identity_unavailable') from None
        identifiers=set(re.findall('[0-9a-f]{64}',group))
        if len(identifiers)!=1 or not identifiers.issubset(allowed_container_ids):
            raise RuntimeError('schema148_unmanaged_host_consumer')
        seen.add(int(fields[0]));observed+=1
    if not required_pids or not required_pids.issubset(seen):
        raise RuntimeError('schema148_host_process_visibility_unverified')
    return observed
