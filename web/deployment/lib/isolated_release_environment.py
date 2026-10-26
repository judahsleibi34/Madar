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


def required_rules(interface, *, execution=False):
    match=lambda left,right:{'match':{'op':'==','left':left,'right':right}}
    nic=match({'meta':{'key':'oifname'}},interface)
    if execution:
        # Permit replies to the parent SSH control connection only. In contrast
        # to preparation v1, established guest-origin connections and public
        # internet/DNS are NOT an execution exception. Input also fences the
        # exact enrolled host-network loopback proxy against external traffic.
        return {
            'forward':[[nic,{'drop':None}]],
            'input':[[match({'meta':{'key':'iifname'}},interface),
                      match({'payload':{'protocol':'tcp','field':'dport'}},22),{'accept':None}],
                     [match({'meta':{'key':'iifname'}},interface),{'drop':None}]],
            'output':[[nic,match({'ct':{'key':'direction'}},'reply'),
                       {'match':{'op':'in','left':{'ct':{'key':'state'}},'right':['established','related']}},{'accept':None}],
                      [nic,{'drop':None}]]}
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


def observe_effect_fence(*, execution=False):
    """Measure the existing exact firewall contract; issue no authority."""
    if os.geteuid()!=0:raise RuntimeError('isolated_release_environment_root_required')
    route=json.loads(run(['/usr/sbin/ip','-json','route','show','default']))
    if len(route)!=1 or not re.fullmatch('[a-zA-Z0-9_-]{1,32}',str(route[0].get('dev'))):
        raise RuntimeError('isolated_release_control_network_invalid')
    interface=route[0]['dev'];wanted=required_rules(interface,execution=execution)
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


# Sources are local to a positively identified disposable guest. Host sockets,
# /proc,/sys,/dev, host roots and arbitrary shared paths cannot be enrolled.
MOUNT_ROOTS=tuple(map(Path,('/etc/madar','/var/lib/madar','/var/lib/madar-control-plane',
    '/opt/madar/control-plane','/opt/madar-test','/srv/madar')))


def measure_bind_source(raw, *, mutable=False):
    """Exact local inode/ownership and immutable bytes; no permission widening.

    Mutable DATA directories bind identity, not changing customer contents.
    This observer cannot enroll or alter policy and grants no execution scope.
    """
    import stat
    path=Path(raw)
    if (not isinstance(raw,str) or not path.is_absolute() or path.as_posix()!=raw
            or '..' in path.parts or not any(path.is_relative_to(root) and path!=root for root in MOUNT_ROOTS)):
        raise RuntimeError('isolated_release_bind_source_forbidden')
    for parent in (path,*path.parents):
        st=parent.lstat()
        if parent.is_symlink() or st.st_uid not in {0,1000,65534} or st.st_mode&0o022:
            raise RuntimeError('isolated_release_bind_source_unprotected')
    st=path.lstat()
    if not (stat.S_ISREG(st.st_mode) or stat.S_ISDIR(st.st_mode)) or (mutable and not stat.S_ISDIR(st.st_mode)):
        raise RuntimeError('isolated_release_bind_source_type_invalid')
    identity={'source':raw,'device':st.st_dev,'inode':st.st_ino,'uid':st.st_uid,'mode':stat.S_IMODE(st.st_mode),
              'mutable_data':mutable}
    if mutable:return identity
    files=sorted(path.rglob('*')) if path.is_dir() else [path]
    if len(files)>8192:raise RuntimeError('isolated_release_bind_source_size')
    inventory={};total=0
    for file in files:
        st=file.lstat()
        if file.is_symlink() or st.st_uid not in {0,1000,65534} or st.st_mode&0o022:
            raise RuntimeError('isolated_release_bind_source_unprotected')
        if stat.S_ISDIR(st.st_mode):continue
        fd=os.open(file,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW|os.O_NONBLOCK)
        with os.fdopen(fd,'rb') as stream:
            opened=os.fstat(stream.fileno())
            if (not stat.S_ISREG(opened.st_mode) or (st.st_dev,st.st_ino)!=(opened.st_dev,opened.st_ino)
                    or opened.st_size>32*1024**2 or total+opened.st_size>128*1024**2):
                raise RuntimeError('isolated_release_bind_source_size_or_identity')
            body=stream.read(opened.st_size+1)
            if len(body)!=opened.st_size:raise RuntimeError('isolated_release_bind_source_changed')
        total+=len(body)
        inventory[file.relative_to(path).as_posix() if file!=path else '.']={
            'sha256':hashlib.sha256(body).hexdigest(),'uid':st.st_uid,'mode':stat.S_IMODE(st.st_mode)}
    from deployment.lib.migration_inventory import digest
    identity['contents_sha256']=digest(inventory)
    return identity


def verify_runtime_scope(scope,rows):
    """Independently enrolled exact actors, limits and mounts, never self-PASS.

    A new/stale/substituted candidate needs fresh root enrollment. The candidate
    cannot enroll itself by writing an allowed-label JSON or sharing a realm.
    """
    from deployment.lib.completed_normal_resources import measured_spec
    if (not isinstance(scope,dict) or not 1<=len(scope)<=128 or set(scope)!={r['Id'] for r in rows}):
        raise RuntimeError('isolated_release_runtime_inventory_changed')
    for row in rows:
        entry=scope[row['Id']];host=row['HostConfig']
        if (not isinstance(entry,dict) or set(entry)!={'name','image','spec_sha256','binds'}
                or entry['name']!=row['Name'] or entry['image']!=row['Image']
                or entry['spec_sha256']!=measured_spec(row) or not isinstance(entry['binds'],dict)
                or not re.fullmatch('sha256:[a-f0-9]{64}',str(entry['image']))
                or type(host.get('Memory')) is not int or not 16*1024**2<=host['Memory']<=2*1024**3
                or type(host.get('NanoCpus')) is not int or not 0<host['NanoCpus']<=2*10**9
                or type(host.get('PidsLimit')) is not int or not 0<host['PidsLimit']<=512
                or host.get('OomKillDisable') is True):
            raise RuntimeError('isolated_release_runtime_spec_or_budget_changed')
        mounts=[m for m in row['Mounts'] if m['Type']=='bind']
        if set(entry['binds'])!={m['Destination'] for m in mounts} or len(entry['binds'])!=len(mounts):
            raise RuntimeError('isolated_release_mount_inventory_changed')
        for mount in mounts:
            expected=entry['binds'][mount['Destination']]
            if not isinstance(expected,dict) or type(expected.get('mutable_data')) is not bool:
                raise RuntimeError('isolated_release_bind_contract_invalid')
            mutable=expected['mutable_data']
            # Writable binds are restricted to application data, never control
            # code, source, keys, configuration or the Docker socket.
            if mutable and not Path(mount['Source']).is_relative_to('/var/lib/madar/storage'):
                raise RuntimeError('isolated_release_mutable_bind_not_application_data')
            if (mount.get('RW') is not mutable or mount.get('Propagation') not in {'rprivate','private'}
                    or measure_bind_source(mount['Source'],mutable=mutable)!=expected):
                raise RuntimeError('isolated_release_bind_source_changed')



def verify_host_interfaces(control_interface,networks):
    """No second physical/tunnel uplink outside the measured control fence."""
    links=json.loads(run(['/usr/sbin/ip','-json','-details','link','show']))
    if (not isinstance(links,list) or not 2<=len(links)<=512
            or len({r.get('ifname') for r in links})!=len(links)):
        raise RuntimeError('isolated_release_host_interface_inventory_invalid')
    bridges={((n.get('Options') or {}).get('com.docker.network.bridge.name') or 'br-'+n['Id'][:12]) for n in networks}
    if any(r.get('ifname')=='docker0' for r in links):
        default=json.loads(run(['/usr/bin/docker','network','inspect','bridge']))
        if (len(default)!=1 or default[0].get('Name')!='bridge' or default[0].get('Driver')!='bridge'
                or default[0].get('Containers') or default[0].get('EnableIPv6')
                or (default[0].get('Options') or {}).get('com.docker.network.bridge.name')!='docker0'):
            raise RuntimeError('isolated_release_default_bridge_not_empty')
        bridges.add('docker0')
    seen={r.get('ifname') for r in links}
    if not {'lo',control_interface}<=seen:
        raise RuntimeError('isolated_release_control_interface_missing')
    for row in links:
        if row['ifname'] in {'lo',control_interface}:continue
        kind=row.get('linkinfo',{}).get('info_kind')
        if kind=='bridge' and row['ifname'] in bridges:continue
        if kind=='veth':continue # Docker endpoints; all actors/networks measured separately.
        raise RuntimeError('isolated_release_unfenced_host_interface')

def observe(policy_path=POLICY):
    if os.geteuid()!=0:raise RuntimeError('isolated_release_environment_root_required')
    path=protected(policy_path,private=True)
    # Exact eight-role origins plus native providers carry independently
    # measured bind identities. Keep a hard bound without truncating inventory.
    if not 0<path.stat().st_size<=128*1024:raise RuntimeError('isolated_release_policy_size_invalid')
    body=path.read_bytes();p=strict_json(body)
    keys={'version','realm_id','guest_uuid','machine_id','root_filesystem_uuid','expires_at',
          'database_container_id','database_system_identifier','denied_database_identifiers'}
    if (not isinstance(p,dict) or type(p.get('version')) is not int or p['version'] not in {1,2}
            or set(p)!=keys|({'runtime_scope'} if p['version']==2 else set())
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
    interface=observe_effect_fence(execution=p['version']==2)
    ids=run(['/usr/bin/docker','ps','-aq','--no-trunc']).decode().split()
    if not ids or len(ids)>128 or p['database_container_id'] not in ids:
        raise RuntimeError('isolated_release_owned_database_required')
    rows=json.loads(run(['/usr/bin/docker','inspect',*ids]));database=None
    if len(rows)!=len(ids) or {r['Id'] for r in rows}!=set(ids):
        raise RuntimeError('isolated_release_actor_inventory_changed')
    if p['version']==2:verify_runtime_scope(p['runtime_scope'],rows)
    network_ids=set();volume_names=set();networks=[]
    for row in rows:
        host=row['HostConfig']
        if (row['Config'].get('Labels',{}).get(REALM_LABEL)!=p['realm_id']
                or host.get('Privileged') or host.get('NetworkMode')=='none'
                or (host.get('NetworkMode')=='host' and (p['version']!=2 or row['Name']!='/madar-release-proxy'))
                or str(host.get('NetworkMode','')).startswith('container:')
                or host.get('PidMode') or host.get('IpcMode')=='host' or host.get('CapAdd')
                or host.get('Devices') or host.get('DeviceRequests')
                or any(b.get('HostIp')!='127.0.0.1' for bs in (host.get('PortBindings') or {}).values() for b in bs)):
            raise RuntimeError('isolated_release_foreign_or_exposed_actor')
        for mount in row.get('Mounts',[]):
            if mount.get('Type')=='volume':volume_names.add(mount['Name'])
            elif mount.get('Type')=='bind' and p['version']==2:pass # Exact independent scope verified above.
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
    if p['version']==2:verify_host_interfaces(interface,networks)
    if database is None or database['Name']!='/supabase-db':raise RuntimeError('isolated_release_database_identity_invalid')
    query="BEGIN READ ONLY; SET LOCAL statement_timeout='3s'; SELECT json_build_array((SELECT system_identifier::text FROM pg_control_system()),shobj_description(oid,'pg_database')) FROM pg_database WHERE datname='postgres'; COMMIT;"
    observed=json.loads(run(['/usr/bin/docker','exec',database['Id'],'psql','-XqAt','-v','ON_ERROR_STOP=1','-U','supabase_admin' if p['version']==2 else 'postgres','-d','postgres','-c',query]))
    if observed!=[p['database_system_identifier'],'madar-isolated-'+p['realm_id']]:
        raise RuntimeError('isolated_release_database_scope_invalid')
    return {**p,'policy_sha256':hashlib.sha256(body).hexdigest(),'control_interface':interface}
