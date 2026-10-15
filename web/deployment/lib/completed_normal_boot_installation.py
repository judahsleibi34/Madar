"""Exact-resource supersession of legacy115 startup controls.

This installer cannot select/start an application, grant writes, migrate SQL or
delete historical units. A complete freshly approved coordinator must invoke it
before changing the installed controller. Source/plan verification is mandatory.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from deployment.lib.completed_normal_admission import ADMISSIONS,OPERATION,digest,encoded,require_fresh_authorization
from deployment.lib.emergency_routing_repair import exclusive
from deployment.lib.provider_recovery_runtime import protected,file_digest
from deployment.lib.completed_normal_profile import profile, LEGACY, MANUAL, APPLICATION, COMMERCIAL

UNITS=Path('/etc/systemd/system')
PROXY='madar-release-proxy.service'
DROPINS=UNITS/(PROXY+'.d')

def unit_bytes(command, *, source=115, target=136):
    return (f'[Unit]\nDescription=Madar accepted schema{source}..{target} boot recovery\n'
        'Requires=docker.service\nWants=madar-release-proxy.service\nAfter=docker.service\nBefore=madar-release-proxy.service\nPartOf=docker.service\n'
        '[Service]\nType=oneshot\nRemainAfterExit=yes\nUser=root\nGroup=root\nUMask=0077\n'
        'Environment=PATH=/usr/sbin:/usr/bin:/sbin:/bin\nEnvironment=LANG=C.UTF-8\n'
        'NoNewPrivileges=yes\nTimeoutStartSec=300\nExecStart='+command+'\n'
        '[Install]\nWantedBy=multi-user.target docker.service\n').encode()

def proxy_bytes(name,command):
    # Dependency directives are additive in systemd drop-ins; an empty value
    # CANNOT reset them. Exact earlier preimages are narrowly superseded below.
    # ExecStartPre DOES support reset and replaces only the legacy actor calls.
    return ('[Unit]\nRequires=docker.service '+name+'\nAfter=docker.service '+name+
        '\n[Service]\nTimeoutStartSec=300\nExecStartPre=\nExecStartPre=+'+command+'\n').encode()

def superseded_dependencies(body,old_units):
    """Remove only literal obsolete unit references, preserving all other bytes."""
    keys={'Requires','Wants','Requisite','BindsTo','PartOf','Upholds','After','Before','OnSuccess','OnFailure'}
    section=None;result=[]
    for line in body.decode().splitlines(keepends=True):
        stripped=line.strip()
        if stripped.startswith('[') and stripped.endswith(']'):section=stripped
        if section=='[Unit]' and '=' in stripped and not stripped.startswith(('#',';')):
            key,value=stripped.split('=',1)
            if key in keys:
                if '\\' in value or '$' in value or '%' in value:
                    raise RuntimeError('completed_boot_dependency_syntax_unreviewed')
                items=value.split()
                if set(items)&set(old_units):
                    remaining=[item for item in items if item not in old_units]
                    if remaining:result.append(key+'='+' '.join(remaining)+'\n')
                    continue
        result.append(line)
    return ''.join(result).encode()

def atomic_resource(path,body,mode):
    descriptor,temporary=tempfile.mkstemp(prefix='.madar-boot-',dir=path.parent)
    try:
        with os.fdopen(descriptor,'wb') as stream:
            os.fchmod(stream.fileno(),mode);stream.write(body);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
        directory=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(directory)
        finally:os.close(directory)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)

class CompletedNormalBootInstallation:
    def __init__(self,contract,document,package,source_guard,operations,*,units=UNITS,admissions=ADMISSIONS):
        if not callable(source_guard):raise RuntimeError('completed_boot_source_guard_required')
        if digest(document)!=contract['plan_sha256']:raise RuntimeError('completed_boot_plan_binding_invalid')
        source_hash=document.get('source_bundle_sha256','')
        if (not re.fullmatch('[0-9a-f]{64}',source_hash)
                or Path(package)!=Path('/var/lib/madar-control-plane/normal-local-preparation')/('normal-source-'+source_hash)):
            raise RuntimeError('completed_boot_package_binding_invalid')
        self.contract,self.document,self.package=contract,document,Path(package)
        self.profile=profile(contract)
        self.source_guard,self.ops=source_guard,operations;self.units=Path(units)
        self.root=Path(admissions)/digest(contract);self.name='madar-compatible-normal-boot-'+digest(contract)[:12]+'.service'
        # A completed136 origin already has a99-compatible-normal drop-in.
        # Its ExecStartPre reset must precede the successor's gate regardless
        # of the two context hashes; lexical hash order is not ownership.
        prefix=('99zzz-compatible-normal-' if self.profile is COMMERCIAL else
            '99zz-compatible-normal-' if self.profile is APPLICATION else
            '99z-compatible-normal-' if self.profile is MANUAL else '99-compatible-normal-')
        self.proxy=self.units/(PROXY+'.d')/(prefix+digest(contract)[:12]+'.conf')
        baseline=document['boot_resources']
        compatible_origin='madar-compatible-normal-boot-'+Path(contract['source_roles']['completion_root']).name[:12]+'.service'
        compatible_units={compatible_origin}
        if self.profile in (APPLICATION, COMMERCIAL):
            # Earlier compatible actors remain historical files. Only actors
            # already measured and superseded by the exact origin receipt may
            # join the currently serving origin in this resource transition.
            original_path=Path(contract['source_roles']['completion_root'])/'boot-preimages.json'
            path=protected(original_path,private=True)
            if file_digest(path)!=contract['historical_files'].get(str(original_path)):
                raise RuntimeError('completed_boot_origin_preimages_changed')
            previous=json.loads(path.read_text())
            compatible_units.update(name for name in previous.get('old_units',[])
                if re.fullmatch('madar-compatible-normal-boot-[0-9a-f]{12}\\.service',name))
        if (set(baseline)!={'files','proxy_dropins','old_units','old_unit_dropins','unit_states'} or not baseline['old_units']
                or any(not (name=='madar-emergency-routing.service' or re.fullmatch('madar-normal-local-(boot|fallback)-[0-9a-f]{12}\\.service',name)
                    or self.profile is not LEGACY and name in compatible_units) for name in baseline['old_units'])
                or set(baseline['unit_states'])!={PROXY,*baseline['old_units']}):
            raise RuntimeError('completed_boot_resource_contract_invalid')
        if set(baseline['old_unit_dropins'])!=set(baseline['old_units']):raise RuntimeError('completed_boot_resource_contract_invalid')
        for name,paths in baseline['old_unit_dropins'].items():
            if any(Path(p).parent!=UNITS/(name+'.d') or not Path(p).name.endswith('.conf') for p in paths):
                raise RuntimeError('completed_boot_resource_inventory_invalid')
        required={str(UNITS/PROXY),*(str(UNITS/name) for name in baseline['old_units']),*baseline['proxy_dropins'],
            *(p for paths in baseline['old_unit_dropins'].values() for p in paths)}
        if set(baseline['files'])!=required or any(Path(p).parent!=DROPINS or not Path(p).name.endswith('.conf') for p in baseline['proxy_dropins']):
            raise RuntimeError('completed_boot_resource_inventory_invalid')
        if self.profile is not LEGACY and any(Path(p).name>=self.proxy.name for p in baseline['proxy_dropins']):
            raise RuntimeError('completed_boot_proxy_gate_order_unreviewed')
        self.baseline=baseline
    def command(self,mode):
        script=self.package/'source/web/scripts/continue_completed_normal_upgrade.py'
        return ('/usr/bin/python3 -I -B '+str(script)+' '+mode+' --source-package '+str(self.package)+
            ' --approved-source '+self.document['source_bundle_sha256']+' --approved-plan '+self.contract['plan_sha256'])
    def paths(self):
        result={self.units/self.name:unit_bytes(self.command('boot'),source=self.profile.source,target=self.profile.target),
                self.proxy:proxy_bytes(self.name,self.command('proxy-gate'))}
        for name in self.baseline['old_units']:
            result[self.units/(name+'.d')/('99-superseded-'+digest(self.contract)[:12]+'.conf')]=(
                '[Unit]\nRefuseManualStart=yes\nConditionPathExists=!'+str(self.root/'boot-installation.json')+'\n').encode()
        return result
    def replacements(self):
        result={}
        for raw in self.baseline['proxy_dropins']:
            path=self.units/Path(raw).relative_to(UNITS)
            retained=self.root/'proxy-originals'/path.name
            original=protected(retained if retained.exists() else path).read_bytes()
            if hashlib.sha256(original).hexdigest()!=self.baseline['files'][raw]['sha256']:
                raise RuntimeError('completed_boot_exact_preimage_changed')
            corrected=superseded_dependencies(original,self.baseline['old_units'])
            if corrected!=original:result[path]=(original,corrected,self.baseline['files'][raw]['mode'])
        return result
    def preflight(self, *, read_only=False):
        self.source_guard()
        if not read_only:require_fresh_authorization(self.contract)
        if os.geteuid()!=0:raise RuntimeError('completed_boot_root_required')
        if any((self.root/name).exists() for name in ('boot-installation.json','boot-preimages.json','boot-installation-failed.json')):
            raise RuntimeError('completed_boot_installation_already_consumed')
        legacy={p.name for kind in ('boot','fallback') for p in self.units.glob('madar-normal-local-'+kind+'-*.service')}
        if self.profile is not LEGACY:
            legacy.update(p.name for p in self.units.glob('madar-compatible-normal-boot-*.service') if p.name!=self.name)
        if (self.units/'madar-emergency-routing.service').exists():legacy.add('madar-emergency-routing.service')
        if legacy!=set(self.baseline['old_units']):raise RuntimeError('completed_boot_legacy_unit_inventory_changed')
        for raw,expected in self.baseline['files'].items():
            path=self.units/Path(raw).relative_to(UNITS)
            st=protected(path).stat()
            if {'sha256':file_digest(path),'uid':st.st_uid,'mode':st.st_mode&0o7777}!=expected:
                raise RuntimeError('completed_boot_exact_preimage_changed')
        current={str(UNITS/(PROXY+'.d')/p.name) for p in (self.units/(PROXY+'.d')).glob('*.conf')}
        if current!=set(self.baseline['proxy_dropins']):raise RuntimeError('completed_boot_proxy_inventory_changed')
        for name,paths in self.baseline['old_unit_dropins'].items():
            current={str(UNITS/(name+'.d')/p.name) for p in (self.units/(name+'.d')).glob('*.conf')}
            if current!=set(paths):raise RuntimeError('completed_boot_legacy_dropin_inventory_changed')
        for name,expected in self.baseline['unit_states'].items():
            if self.ops.systemctl_state(name)!=expected:raise RuntimeError('completed_boot_unit_state_changed')
        if any(p.exists() or p.is_symlink() for p in self.paths()):
            raise RuntimeError('completed_boot_installation_already_consumed')
        self.replacements() # Reject unreviewed dependency syntax before effects.
        return {'production_modified':False,'old_units_preserved':self.baseline['old_units']}
    def installed(self):
        self.source_guard()
        record=json.loads(protected(self.root/'boot-installation.json',private=True).read_text())
        expected={str(p):hashlib.sha256(body).hexdigest() for p,body in self.paths().items()}
        replaced=self.replacements()
        superseded={str(p):hashlib.sha256(new).hexdigest() for p,(_,new,_) in replaced.items()}
        if (record!={'operation':self.profile.operation,'context_sha256':digest(self.contract),'resources':expected,
            'superseded_proxy_dropins':superseded,'superseded_units':self.baseline['old_units'],'historical_units_deleted':False}):
            raise RuntimeError('completed_boot_installation_attestation_changed')
        if any(file_digest(protected(Path(p)))!=value for p,value in expected.items()):
            raise RuntimeError('completed_boot_installed_resource_changed')
        for raw,baseline in self.baseline['files'].items():
            path=self.units/Path(raw).relative_to(UNITS);st=protected(path).stat()
            expected_original=dict(baseline,sha256=superseded[str(path)]) if str(path) in superseded else baseline
            if {'sha256':file_digest(path),'uid':st.st_uid,'mode':st.st_mode&0o7777}!=expected_original:
                raise RuntimeError('completed_boot_preserved_resource_changed')
        for name,paths in self.baseline['old_unit_dropins'].items():
            actual={str(UNITS/(name+'.d')/p.name) for p in (self.units/(name+'.d')).glob('*.conf')}
            own=str(UNITS/(name+'.d')/('99-superseded-'+digest(self.contract)[:12]+'.conf'))
            if actual!=set(paths)|{own}:raise RuntimeError('completed_boot_legacy_dropin_inventory_changed')
        actual={str(p) for p in (self.units/(PROXY+'.d')).glob('*.conf')}
        expected_inventory={str(self.units/Path(raw).relative_to(UNITS)) for raw in self.baseline['proxy_dropins']}|{str(self.proxy)}
        if actual!=expected_inventory:
            raise RuntimeError('completed_boot_proxy_inventory_changed')
        if any(self.ops.systemctl_state(n)['enabled']!='disabled' for n in self.baseline['old_units']):
            raise RuntimeError('completed_boot_old_activation_not_disabled')
        if self.ops.systemctl_state(self.name)['enabled']!='enabled':raise RuntimeError('completed_boot_new_activation_missing')
        # Physical /etc inventories alone cannot detect /run or vendor
        # overrides. Bind the actual fragments/drop-ins loaded by systemd.
        for name in [self.name,*self.baseline['old_units']]:
            raw=self.ops.command('completed_boot_effective_actor',['systemctl','show',name,
                '--property=FragmentPath,DropInPaths','--no-pager']).stdout
            loaded=dict(line.split('=',1) for line in raw.splitlines() if '=' in line)
            expected_dropins=set() if name==self.name else set(self.baseline['old_unit_dropins'][name])|{
                str(UNITS/(name+'.d')/('99-superseded-'+digest(self.contract)[:12]+'.conf'))}
            if (loaded.get('FragmentPath')!=str(UNITS/name)
                    or set(loaded.get('DropInPaths','').split())!=expected_dropins):
                raise RuntimeError('completed_boot_effective_actor_controls_changed')
        raw=self.ops.command('completed_boot_effective_proxy',['systemctl','show',PROXY,'--property=Requires,ExecStartPre,DropInPaths','--no-pager']).stdout
        values=dict(line.split('=',1) for line in raw.splitlines() if '=' in line)
        requires=set(values.get('Requires','').split())
        if (self.name not in requires or set(self.baseline['old_units'])&requires
                or self.command('proxy-gate') not in values.get('ExecStartPre','')
                or set(values.get('DropInPaths','').split())!=set(self.baseline['proxy_dropins'])|{str(self.proxy)}):
            raise RuntimeError('completed_boot_effective_proxy_controls_changed')
        return record
    def install(self):
        # The complete coordinator owns deployment/upgrade locks throughout.
        # No unit is started and no application/traffic/write state is changed.
        self.preflight();paths=self.paths();replaced=self.replacements()
        exclusive(self.root/'boot-preimages.json',encoded(self.baseline))
        created=[];replaced_paths=[]
        try:
            originals=self.root/'proxy-originals';originals.mkdir(mode=0o700)
            for path,(original,_,_) in replaced.items():exclusive(originals/path.name,original)
            for path,body in paths.items():
                path.parent.mkdir(mode=0o755,exist_ok=True)
                if path.parent.is_symlink() or path.parent.stat().st_uid!=0 or path.parent.stat().st_mode&0o022:
                    raise RuntimeError('completed_boot_destination_untrusted')
                exclusive(path,body);created.append(path);path.chmod(0o644)
            self.ops.command('completed_boot_unit_validation',['systemd-analyze','verify',str(self.units/self.name)])
            for path,(original,new,mode) in replaced.items():
                if protected(path).read_bytes()!=original:raise RuntimeError('completed_boot_exact_preimage_changed')
                # Mark compensation responsibility before the atomic rename.
                replaced_paths.append(path);atomic_resource(path,new,mode)
            # Receipt closes every old ConditionPathExists before daemon-reload.
            exclusive(self.root/'boot-installation.json',encoded({'operation':self.profile.operation,'context_sha256':digest(self.contract),
                'resources':{str(p):hashlib.sha256(b).hexdigest() for p,b in paths.items()},
                'superseded_proxy_dropins':{str(p):hashlib.sha256(new).hexdigest() for p,(_,new,_) in replaced.items()},
                'superseded_units':self.baseline['old_units'],'historical_units_deleted':False}))
            for name in self.baseline['old_units']:self.ops.command('completed_boot_disable_old',['systemctl','disable',name])
            self.ops.command('completed_boot_reload',['systemctl','daemon-reload'])
            self.ops.command('completed_boot_enable_new',['systemctl','enable',self.name])
            self.installed()
        except Exception as error:
            # Restore the exact approved earlier drop-in preimages and retain
            # generated additions as audit data. Original units stay unchanged.
            exclusive(self.root/'boot-installation-failed.json',encoded({'operation':self.profile.operation,'context_sha256':digest(self.contract),
                'exception_type':type(error).__name__,'phase':'boot_resource_installation',
                'retained_generated_resources':{str(p):hashlib.sha256(paths[p]).hexdigest() for p in created},'database_restored':False}))
            for path in reversed(replaced_paths):
                original,new,mode=replaced[path];current=protected(path).read_bytes()
                if current not in (original,new):raise RuntimeError('completed_boot_rollback_resource_changed')
                atomic_resource(path,original,mode)
            for path in reversed(created):
                if file_digest(protected(path))!=hashlib.sha256(paths[path]).hexdigest():
                    raise RuntimeError('completed_boot_rollback_resource_changed')
                exclusive(self.root/('retained-'+path.relative_to(self.units).as_posix().replace('/','_')),path.read_bytes());path.unlink()
            self.ops.command('completed_boot_disable_failed',['systemctl','disable',self.name],check=False)
            for name,state in self.baseline['unit_states'].items():
                if name!=PROXY and state['enabled']=='enabled':self.ops.command('completed_boot_restore_activation',['systemctl','enable',name])
            self.ops.command('completed_boot_rollback_reload',['systemctl','daemon-reload'])
            raise
        return self.installed()

    def restore_application_preimages(self):
        """Exact boot backout for the separately approved no-SQL operation."""
        if self.profile is not APPLICATION:
            raise RuntimeError('completed_boot_application_restore_operation_invalid')
        require_fresh_authorization(self.contract)
        self.installed()
        paths=self.paths();replaced=self.replacements()
        exclusive(self.root/'application-boot-restore-intent.json',encoded({
            'operation':self.profile.operation,'context_sha256':digest(self.contract),
            'database_restored':False}))
        self.ops.command('application_boot_disable_successor',['systemctl','disable',self.name])
        for path,(original,new,mode) in replaced.items():
            if protected(path).read_bytes()!=new:raise RuntimeError('completed_boot_rollback_resource_changed')
            atomic_resource(path,original,mode)
        for path,body in paths.items():
            if protected(path).read_bytes()!=body:raise RuntimeError('completed_boot_rollback_resource_changed')
            exclusive(self.root/('retained-'+path.relative_to(self.units).as_posix().replace('/','_')),body)
            path.unlink()
        for name,state in self.baseline['unit_states'].items():
            if name!=PROXY and state['enabled']=='enabled':
                self.ops.command('application_boot_restore_origin',['systemctl','enable',name])
        self.ops.command('application_boot_restore_reload',['systemctl','daemon-reload'])
        for raw,value in self.baseline['files'].items():
            if file_digest(protected(self.units/Path(raw).relative_to(UNITS)))!=value['sha256']:
                raise RuntimeError('completed_boot_rollback_resource_changed')
        exclusive(self.root/'application-boot-restored.json',encoded({
            'operation':self.profile.operation,'context_sha256':digest(self.contract),
            'database_restored':False,'historical_units_deleted':False}))
