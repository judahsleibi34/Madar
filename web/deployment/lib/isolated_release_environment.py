"""Positive non-production environment observation; not operation authorization.

Root provisions this policy only inside an owned disposable KVM guest. No JSON
PASS, hostname alone or environment variable admits a protected operation.
Production issuers, profiles and dispatch remain unchanged.
"""
import hashlib,json,os,re,subprocess,uuid
from pathlib import Path
from datetime import datetime,timezone
from deployment.lib.provider_recovery_runtime import protected
from deployment.lib.migration_inventory import strict_json

POLICY=Path('/etc/madar/isolated-release-test.json')
TABLE='madar_release_test'
REALM_LABEL='com.madar.test.realm'


def run(args):
    return subprocess.check_output(args,env={'PATH':os.defpath,'HOME':'/nonexistent','LANG':'C'},timeout=15)


def required_rules(interface):
    match=lambda left,right:{'match':{'op':'==','left':left,'right':right}}
    nic=match({'meta':{'key':'oifname'}},interface)
    return {
        'forward':[[nic,{'drop':None}]],
        'output':[
            [nic,{'match':{'op':'in','left':{'ct':{'key':'state'}},'right':['established','related']}},{'accept':None}],
            [nic,match({'payload':{'protocol':'ip','field':'daddr'}},'10.0.2.3'),
             match({'payload':{'protocol':'udp','field':'dport'}},53),{'accept':None}],
            [nic,{'match':{'op':'==','left':{'payload':{'protocol':'ip','field':'daddr'}},'right':{'set':[
                {'prefix':{'addr':'10.0.0.0','len':8}},{'prefix':{'addr':'169.254.0.0','len':16}},
                {'prefix':{'addr':'172.16.0.0','len':12}},{'prefix':{'addr':'192.168.0.0','len':16}}]}}},{'drop':None}],
            [nic,match({'meta':{'key':'nfproto'}},'ipv6'),{'drop':None}]]}


def observe_effect_fence():
    """Measure the existing exact firewall contract; issue no authority."""
    if os.geteuid()!=0:raise RuntimeError('isolated_release_environment_root_required')
    route=json.loads(run(['/usr/sbin/ip','-json','route','show','default']))
    if len(route)!=1 or not re.fullmatch('[a-zA-Z0-9_-]{1,32}',str(route[0].get('dev'))):
        raise RuntimeError('isolated_release_control_network_invalid')
    interface=route[0]['dev'];wanted=required_rules(interface)
    table=json.loads(run(['/usr/sbin/nft','--stateless','--json','list','table','inet',TABLE]))['nftables']
    chains={};rules={k:[] for k in wanted}
    for row in table:
        if 'chain' in row:
            c=row['chain'];chains[c['name']]=c
        if 'rule' in row:
            r=row['rule']
            if r['chain'] not in rules:raise RuntimeError('isolated_release_unreviewed_firewall_rule')
            rules[r['chain']].append(r['expr'])
    if set(chains)!=set(wanted) or rules!=wanted or any(
            chains[k].get('hook')!=k or chains[k].get('type')!='filter'
            or chains[k].get('prio')!=200 or chains[k].get('policy')!='accept' for k in wanted):
        raise RuntimeError('isolated_release_effect_fencing_invalid')
    return interface


def observe(policy_path=POLICY):
    if os.geteuid()!=0:raise RuntimeError('isolated_release_environment_root_required')
    path=protected(policy_path,private=True)
    if not 0<path.stat().st_size<=16384:raise RuntimeError('isolated_release_policy_size_invalid')
    body=path.read_bytes();p=strict_json(body)
    keys={'version','realm_id','guest_uuid','machine_id','root_filesystem_uuid','expires_at',
          'database_container_id','database_system_identifier','denied_database_identifiers'}
    if (not isinstance(p,dict) or set(p)!=keys or type(p['version']) is not int or p['version']!=1
            or any(not re.fullmatch('[0-9a-f-]{36}',str(p[k])) for k in ('realm_id','guest_uuid','root_filesystem_uuid'))
            or not re.fullmatch('[0-9a-f]{32}',str(p['machine_id']))
            or not re.fullmatch('[0-9a-f]{64}',str(p['database_container_id']))
            or not re.fullmatch('[1-9][0-9]{0,19}',str(p['database_system_identifier']))
            or not isinstance(p['denied_database_identifiers'],list) or not p['denied_database_identifiers']
            or any(not re.fullmatch('[1-9][0-9]{0,19}',str(v)) for v in p['denied_database_identifiers'])
            or p['database_system_identifier'] in p['denied_database_identifiers']):
        raise RuntimeError('isolated_release_policy_invalid')
    try:
        if any(str(uuid.UUID(p[k]))!=p[k] for k in ('realm_id','guest_uuid','root_filesystem_uuid')):raise ValueError()
    except ValueError:raise RuntimeError('isolated_release_policy_invalid') from None
    try:expiry=datetime.fromisoformat(p['expires_at'])
    except (ValueError,TypeError):raise RuntimeError('isolated_release_policy_expiration_invalid') from None
    now=datetime.now(timezone.utc)
    if expiry.tzinfo is None or not now<expiry<=now+__import__('datetime').timedelta(hours=4):
        raise RuntimeError('isolated_release_policy_expired_or_unbounded')
    if (run(['/usr/bin/systemd-detect-virt']).decode().strip()!='kvm'
            or run(['/bin/hostname']).decode().strip()!='madar-release-test'
            or Path('/sys/class/dmi/id/product_uuid').read_text().strip().lower()!=p['guest_uuid']
            or Path('/etc/machine-id').read_text().strip()!=p['machine_id']):
        raise RuntimeError('isolated_release_guest_identity_invalid')
    fs=run(['/usr/bin/findmnt','-n','-o','SOURCE,FSTYPE,UUID','/']).decode().split()
    if len(fs)!=3 or not fs[0].startswith('/dev/vd') or fs[1]!='ext4' or fs[2]!=p['root_filesystem_uuid']:
        raise RuntimeError('isolated_release_root_filesystem_invalid')
    interface=observe_effect_fence()
    ids=run(['/usr/bin/docker','ps','-aq','--no-trunc']).decode().split()
    if not ids or len(ids)>128 or p['database_container_id'] not in ids:
        raise RuntimeError('isolated_release_owned_database_required')
    rows=json.loads(run(['/usr/bin/docker','inspect',*ids]));database=None
    if len(rows)!=len(ids) or {r['Id'] for r in rows}!=set(ids):
        raise RuntimeError('isolated_release_actor_inventory_changed')
    network_ids=set();volume_names=set()
    for row in rows:
        host=row['HostConfig']
        if (row['Config'].get('Labels',{}).get(REALM_LABEL)!=p['realm_id']
                or host.get('Privileged') or host.get('NetworkMode') in {'host','none'}
                or str(host.get('NetworkMode','')).startswith('container:')
                or host.get('PidMode') or host.get('IpcMode')=='host' or host.get('CapAdd')
                or host.get('Devices') or host.get('DeviceRequests')
                or any(b.get('HostIp')!='127.0.0.1' for bs in (host.get('PortBindings') or {}).values() for b in bs)):
            raise RuntimeError('isolated_release_foreign_or_exposed_actor')
        for mount in row.get('Mounts',[]):
            if mount.get('Type')=='volume':volume_names.add(mount['Name'])
            elif mount.get('Type')!='tmpfs':
                # No arbitrary host roots, sockets, production or shared mounts.
                # Exact root-owned test inputs are introduced by a separate
                # reviewed preparation interface, not this environment policy.
                raise RuntimeError('isolated_release_unowned_mount')
        network_ids.update(v['NetworkID'] for v in row['NetworkSettings']['Networks'].values())
        if row['Id']==p['database_container_id']:database=row
    if network_ids:
        networks=json.loads(run(['/usr/bin/docker','network','inspect',*sorted(network_ids)]))
        if ({v['Id'] for v in networks}!=network_ids or any(
                n.get('Driver')!='bridge' or n.get('EnableIPv6')
                or (n.get('Labels') or {}).get(REALM_LABEL)!=p['realm_id'] for n in networks)):
            raise RuntimeError('isolated_release_unowned_network')
    if volume_names:
        volumes=json.loads(run(['/usr/bin/docker','volume','inspect',*sorted(volume_names)]))
        if ({v['Name'] for v in volumes}!=volume_names or any(
                v.get('Driver')!='local' or v.get('Options')
                or (v.get('Labels') or {}).get(REALM_LABEL)!=p['realm_id'] for v in volumes)):
            raise RuntimeError('isolated_release_unowned_volume')
    if database is None or database['Name']!='/supabase-db':raise RuntimeError('isolated_release_database_identity_invalid')
    query="BEGIN READ ONLY; SET LOCAL statement_timeout='3s'; SELECT json_build_array((SELECT system_identifier::text FROM pg_control_system()),shobj_description(oid,'pg_database')) FROM pg_database WHERE datname='postgres'; COMMIT;"
    observed=json.loads(run(['/usr/bin/docker','exec',database['Id'],'psql','-XqAt','-v','ON_ERROR_STOP=1','-U','postgres','-d','postgres','-c',query]))
    if observed!=[p['database_system_identifier'],'madar-isolated-'+p['realm_id']]:
        raise RuntimeError('isolated_release_database_scope_invalid')
    return {**p,'policy_sha256':hashlib.sha256(body).hexdigest(),'control_interface':interface}
