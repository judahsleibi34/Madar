"""Fixed canonical160 private HTTP/PG transport; no issuer or executor.

The gateway runs an immutable configuration baked into the accepted frontend
image. It has no host ports, authority, database credentials or writable binds.
Its internal client bridge is separate from the measured original provider
bridge. The original public gateway is never used for private acceptance.
"""
from urllib.parse import urlsplit,parse_qs,unquote

NATIVE_NETWORK='madar-local-supabase_default'
CLIENT_NETWORK='madar-supabase-client'
CONFIG='/etc/nginx/private-provider160.conf'
GATEWAY_ENV={'PATH','NGINX_VERSION','PKG_RELEASE','DYNPKG_RELEASE','NJS_VERSION','NJS_RELEASE','ACME_VERSION'}


def environment(items):
    result={}
    for raw in items or []:
        key,sep,value=raw.partition('=')
        if not sep or key in result:raise RuntimeError('completed_private_provider_environment_invalid')
        result[key]=value
    return result


def require_calendar_environment(env, *, gateway_name, system_identifier):
    """Require explicit protected credentials/config; never discover or grant them."""
    try:
        uri=urlsplit(env.get('MADAR_CALENDAR_DATABASE_DSN',''))
        options=parse_qs(uri.query,strict_parsing=True,keep_blank_values=True)
        if (uri.scheme not in {'postgres','postgresql'} or uri.fragment
                or unquote(uri.username or '')!='authenticator' or not uri.password
                or uri.hostname!=gateway_name or uri.port!=5432 or uri.path!='/postgres'
                or set(options)!={'sslmode'} or options['sslmode'] not in
                   (['disable'],['require'],['verify-ca'],['verify-full'])
                or env.get('MADAR_CALENDAR_DATABASE_SYSTEM_IDENTIFIER')!=system_identifier
                or env.get('SUPABASE_URL')!='http://'+gateway_name+':8000'):
            raise ValueError()
    except (ValueError,TypeError):
        raise RuntimeError('completed_private_calendar_transport_invalid') from None


def verify_gateway(row, *, source_sha, image):
    config=row.get('Config',{});host=row.get('HostConfig',{})
    env=environment(config.get('Env'))
    if (row.get('Image')!=image or config.get('Labels',{}).get('org.opencontainers.image.revision')!=source_sha
            or not set(env)<=GATEWAY_ENV or config.get('User')!='nginx'
            or config.get('Entrypoint')!=['nginx']
            or config.get('Cmd')!=['-c',CONFIG,'-g','daemon off;']):
        raise RuntimeError('completed_private_gateway_configuration_invalid')
    if (host.get('Privileged') is not False or host.get('ReadonlyRootfs') is not True
            or sorted(host.get('CapDrop') or [])!=['ALL'] or host.get('CapAdd')
            or sorted(host.get('SecurityOpt') or [])!=['no-new-privileges:true']
            or host.get('Init') is not True or host.get('Memory')!=128*1024**2
            or host.get('NanoCpus')!=250_000_000 or host.get('PidsLimit')!=64
            or host.get('Devices') or host.get('DeviceRequests') or host.get('PidMode')
            or host.get('IpcMode') not in {None,'','private','none'} or host.get('UTSMode')
            or host.get('RestartPolicy',{}).get('Name')!='no'
            or host.get('PublishAllPorts') or host.get('PortBindings')
            or any(row.get('NetworkSettings',{}).get('Ports',{}).values())
            or host.get('ExtraHosts') or host.get('Dns') or host.get('DnsSearch') or host.get('DnsOptions')
            or host.get('NetworkMode') not in {NATIVE_NETWORK,CLIENT_NETWORK}
            or set(row.get('NetworkSettings',{}).get('Networks',{}))!={NATIVE_NETWORK,CLIENT_NETWORK}
            or host.get('Tmpfs')!={'/tmp':'rw,noexec,nosuid,size=16m,mode=1777'} or row.get('Mounts')!=[]):
        raise RuntimeError('completed_private_gateway_isolation_invalid')


def verify_topology(inventory, binding, rows):
    """Measure the exact gateway, DNS owner and private backend configuration."""
    import re
    actors=inventory['containers']
    if 'candidate:provider-gateway' not in actors:return
    gateway=actors['candidate:provider-gateway'];name=gateway['name']
    if re.fullmatch('madar-schema160-'+binding['context_sha256'][:16]+'-(blue|green)-provider-gateway',name) is None:
        raise RuntimeError('completed_private_gateway_identity_invalid')
    actual={row['Id']:row for row in rows}
    verify_gateway(actual[gateway['id']],source_sha=binding['source_sha'],image=gateway['image'])
    for net in (NATIVE_NETWORK,CLIENT_NETWORK):
        if gateway['networks'].get(net)!=inventory['target_networks'][net]:
            raise RuntimeError('completed_private_gateway_network_changed')
    owners=set()
    for row in rows:
        peer=row.get('NetworkSettings',{}).get('Networks',{}).get(CLIENT_NETWORK)
        if peer is None:continue
        if name in {row.get('Name','').lstrip('/'),*(peer.get('Aliases') or []),*(peer.get('DNSNames') or [])}:
            owners.add(row['Id'])
    if owners!={gateway['id']}:raise RuntimeError('completed_private_gateway_dns_ambiguous')
    backend=actual[actors['candidate:backend']['id']]
    host=backend['HostConfig']
    if host.get('ExtraHosts') or host.get('Dns') or host.get('DnsSearch') or host.get('DnsOptions'):
        raise RuntimeError('completed_private_calendar_dns_override')
    require_calendar_environment(environment(backend['Config'].get('Env')),
        gateway_name=name,system_identifier=binding['system_identifier'])
