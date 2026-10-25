"""Measured original-provider probes for the existing maintenance coordinator.

No issuer, registration, SQL executor or caller PASS interface. The approved
plan binds private credentials for designated original acceptance accounts.
Credentials remain root-private; receipts contain only identity/data digests.
"""
import base64
import hashlib
import hmac
import json
import re
import struct
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request,build_opener,ProxyHandler

from deployment.lib.completed_normal_admission import digest,encoded,validate_provider_preparation,require_candidate_authority
from deployment.lib.completed_normal_profile import RECONCILED
from deployment.lib.emergency_routing_repair import exclusive
from deployment.lib.provider_recovery_runtime import protected,file_digest,readonly_configuration
from deployment.lib.schema150_provider_adapter import private_json,NoRedirect,_env,Schema150ProviderAdapter
from deployment.lib.schema150_provider_lifecycle import validate_binding,release_contract

SUBJECT_KEYS={'auth_id','user_id','tenant_id','email','password','factor_id','totp_secret','bucket','object','object_sha256'}
UUID_RE=r'[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}'


def validate_subjects(value):
    """Exact designated accounts/data, never a probe result or arbitrary URL."""
    if not isinstance(value,list) or not 2<=len(value)<=4:
        raise RuntimeError('maintenance_original_subjects_required')
    identities=set();tenants=set()
    for subject in value:
        if not isinstance(subject,dict) or set(subject)!=SUBJECT_KEYS:
            raise RuntimeError('maintenance_original_subject_invalid')
        if (any(not re.fullmatch(UUID_RE,str(subject[k])) for k in ('auth_id','factor_id'))
                or any(type(subject[k]) is not int or subject[k]<=0 for k in ('user_id','tenant_id'))
                or not isinstance(subject['email'],str) or not 3<=len(subject['email'])<=254
                or not isinstance(subject['password'],str) or not 8<=len(subject['password'])<=1024
                or not re.fullmatch('[A-Z2-7]{16,128}',str(subject['totp_secret']))
                or not re.fullmatch('[a-zA-Z0-9_-]{1,100}',str(subject['bucket']))
                or not isinstance(subject['object'],str) or not 1<=len(subject['object'])<=512
                or any(not re.fullmatch('[a-zA-Z0-9_.-]+',part) or part in {'.','..'}
                       for part in subject['object'].split('/'))
                or not re.fullmatch('[0-9a-f]{64}',str(subject['object_sha256']))
                or subject['auth_id'] in identities):
            raise RuntimeError('maintenance_original_subject_invalid')
        identities.add(subject['auth_id']);tenants.add(subject['tenant_id'])
    if len(tenants)!=len(value):raise RuntimeError('maintenance_original_distinct_tenants_required')
    return json.loads(encoded(value))


def totp(secret,now):
    key=base64.b32decode(secret+'='*(-len(secret)%8))
    body=hmac.new(key,struct.pack('>Q',int(now)//30),hashlib.sha1).digest();offset=body[-1]&15
    return f'{(struct.unpack(">I",body[offset:offset+4])[0]&0x7fffffff)%1000000:06d}'


def observe_subjects(subjects,endpoints,anon_key):
    """Actual password/MFA/user-object/tenant isolation; no account creation.

    Endpoints come only from the adapter's measured original containers. Do not
    retry uncertain challenge/verification or refresh effects. Auth session
    creation is confined to the explicitly approved acceptance identities.
    """
    subjects=validate_subjects(subjects)
    if set(endpoints)!={'auth','rest','storage'}:
        raise RuntimeError('maintenance_private_endpoints_invalid')
    for name,port in (('auth',9999),('rest',3000),('storage',5000)):
        import ipaddress
        try:
            from urllib.parse import urlsplit
            uri=urlsplit(endpoints[name]);address=ipaddress.ip_address(uri.hostname)
            if (uri.scheme!='http' or address.version!=4 or not address.is_private or address.is_loopback
                    or address.is_link_local or uri.port!=port or uri.path or uri.query or uri.fragment or uri.username):
                raise ValueError()
        except (ValueError,TypeError):raise RuntimeError('maintenance_private_endpoints_invalid') from None
    opener=build_opener(ProxyHandler({}),NoRedirect())
    overall_deadline=time.monotonic()+180
    def call(service,method,path,*,body=None,token=None,expected=(200,),binary=False):
        remaining=overall_deadline-time.monotonic()
        if remaining<=0:raise RuntimeError('maintenance_original_probe_deadline')
        headers={'Content-Type':'application/json','apikey':anon_key}
        if token:headers['Authorization']='Bearer '+token
        request=Request(endpoints[service]+path,data=json.dumps(body).encode() if body is not None else None,
            headers=headers,method=method)
        try:response=opener.open(request,timeout=min(5,remaining))
        except HTTPError as error:response=error
        with response:
            # Object probes are bounded to designated small acceptance bytes;
            # arbitrary large production objects are never read into root RAM.
            raw=bytearray();body_deadline=min(overall_deadline,time.monotonic()+15)
            while len(raw)<=2*1024**2:
                if time.monotonic()>body_deadline:raise RuntimeError('maintenance_original_probe_deadline')
                chunk=response.read1(min(16384,2*1024**2+1-len(raw)))
                if not chunk:break
                raw.extend(chunk)
            raw=bytes(raw)
            if response.status not in expected or len(raw)>2*1024**2:
                raise RuntimeError('maintenance_original_provider_probe_failed')
            if binary:return raw
            try:return json.loads(raw)
            except ValueError:raise RuntimeError('maintenance_original_provider_response_invalid') from None
    observations=[]
    # Use a new TOTP interval to avoid reusing the account's previous accepted
    # code. No retries after verification or after an unknown HTTP outcome.
    interval=int(time.time())//30
    deadline=time.monotonic()+32
    while int(time.time())//30==interval:
        if time.monotonic()>deadline:raise RuntimeError('maintenance_original_totp_clock_stalled')
        time.sleep(.2)
    for subject in subjects:
        session=call('auth','POST','/token?grant_type=password',body={k:subject[k] for k in ('email','password')})
        user=session.get('user',{})
        if user.get('id')!=subject['auth_id']:
            raise RuntimeError('maintenance_original_auth_identity_changed')
        factors=user.get('factors',[])
        if not any(f.get('id')==subject['factor_id'] and f.get('status')=='verified'
                   and f.get('factor_type')=='totp' for f in factors):
            raise RuntimeError('maintenance_original_mfa_factor_changed')
        challenge=call('auth','POST','/factors/'+subject['factor_id']+'/challenge',body={},token=session['access_token'])
        elevated=call('auth','POST','/factors/'+subject['factor_id']+'/verify',token=session['access_token'],
            body={'challenge_id':challenge['id'],'code':totp(subject['totp_secret'],time.time())})
        token=elevated['access_token']
        # The native Auth endpoint validates the actual bearer. Decoding alone
        # is not authentication, and neither this token nor its claims is a
        # release/write-authority credential.
        current=call('auth','GET','/user',token=token)
        if current.get('id')!=subject['auth_id']:raise RuntimeError('maintenance_original_auth_identity_changed')
        try:claims=json.loads(base64.urlsafe_b64decode(token.split('.')[1]+'==='))
        except (ValueError,IndexError):raise RuntimeError('maintenance_original_mfa_token_invalid') from None
        if claims.get('aal')!='aal2' or claims.get('sub')!=subject['auth_id']:
            raise RuntimeError('maintenance_original_mfa_aal2_required')
        refreshed=call('auth','POST','/token?grant_type=refresh_token',body={'refresh_token':elevated['refresh_token']})
        if refreshed.get('refresh_token') in (None,elevated['refresh_token']):
            raise RuntimeError('maintenance_original_refresh_rotation_required')
        path='/object/'+quote(subject['bucket'],safe='')+'/'+quote(subject['object'],safe='/')
        raw=call('storage','GET',path,token=token,binary=True)
        if hashlib.sha256(raw).hexdigest()!=subject['object_sha256']:
            raise RuntimeError('maintenance_original_object_changed')
        call('storage','GET',path,token=anon_key,expected=(400,403,404))
        own=call('rest','GET','/tenant_memberships?select=tenant_id,user_id,auth_id,status&tenant_id=eq.'+
            str(subject['tenant_id'])+'&user_id=eq.'+str(subject['user_id']),token=token)
        if own!=[{k:subject[k] for k in ('tenant_id','user_id','auth_id')}|{'status':'active'}]:
            raise RuntimeError('maintenance_original_tenant_relationship_changed')
        for foreign in subjects:
            if foreign['tenant_id']==subject['tenant_id']:continue
            value=call('rest','GET','/tenant_memberships?select=tenant_id,user_id,auth_id&tenant_id=eq.'+
                str(foreign['tenant_id']),token=token)
            if value!=[]:raise RuntimeError('maintenance_original_tenant_isolation_failed')
        observations.append({'auth_id':subject['auth_id'],'tenant_id':subject['tenant_id'],
            'user_id':subject['user_id'],'factor_id':subject['factor_id'],'object_sha256':subject['object_sha256']})
    return observations


class CompletedNormalMaintenanceGuards:
    def __init__(self,actor):
        if validate_provider_preparation(actor.contract) is not RECONCILED:
            raise RuntimeError('maintenance_private_profile_required')
        self.actor=actor;self.driver=None
        expected=actor.document.get('original_provider_probe_sha256')
        if not re.fullmatch('[0-9a-f]{64}',str(expected)):
            raise RuntimeError('maintenance_original_probe_binding_required')
        path=protected(actor.package/'original-provider-probes.json',private=True)
        if not 0<path.stat().st_size<=65536:raise RuntimeError('maintenance_original_probe_size_invalid')
        body=path.read_bytes()
        if len(body)>65536 or hashlib.sha256(body).hexdigest()!=expected:
            raise RuntimeError('maintenance_original_probe_bytes_changed')
        value=json.loads(body)
        if (not isinstance(value,dict) or set(value)!={'version','system_identifier','subjects'}
                or type(value['version']) is not int or value['version']!=1
                or value['system_identifier']!=actor.contract['database']['system_identifier']):
            raise RuntimeError('maintenance_original_probe_scope_changed')
        self.subjects=validate_subjects(value['subjects']);self.probe_sha256=expected

    def bind(self,driver):
        from deployment.lib.completed_normal_execution import CompletedNormalUpgrade
        if self.driver is not None or type(driver) is not CompletedNormalUpgrade or driver.actor is not self.actor:
            raise RuntimeError('maintenance_private_driver_binding_invalid')
        self.driver=driver

    def provider(self,binding,purpose):
        binding=validate_binding(binding)
        provider=getattr(self.driver,'provider_adapter',None)
        if (type(provider) is not Schema150ProviderAdapter or provider.binding!=binding
                or provider.contract!=self.actor.contract or provider.runtime is not self.actor.runtime):
            raise RuntimeError('maintenance_private_provider_binding_invalid')
        self.actor.guard();provider.require_authority(binding,purpose=purpose)
        return provider

    def material(self,provider):
        # Fixed validated UUIDs/integers only. Password verifiers and MFA secrets
        # never leave PostgreSQL; receipts contain their one-way row digest.
        clauses=[]
        for s in self.subjects:
            clauses.append("select jsonb_build_object('auth_id',u.id,'email',u.email,'password',u.encrypted_password,"
                "'factor',f.id,'factor_secret',f.secret,'factor_status',f.status,'tenant',m.tenant_id,"
                "'user',m.user_id,'role',m.role,'membership_status',m.status)::text value "
                "from auth.users u join auth.mfa_factors f on f.user_id=u.id "
                "join public.tenant_memberships m on m.auth_id=u.id "
                f"where u.id='{s['auth_id']}' and f.id='{s['factor_id']}' and m.tenant_id={s['tenant_id']} and m.user_id={s['user_id']}")
        sql="select json_build_object('count',count(*),'sha256',encode(sha256(convert_to(coalesce(string_agg(value,'' order by value collate \"C\"),''),'UTF8')),'hex')) from ("+' union all '.join(clauses)+') q;'
        value=json.loads(provider._sql('BEGIN READ ONLY;'+sql+'COMMIT;'))
        if value.get('count')!=len(self.subjects) or not re.fullmatch('[0-9a-f]{64}',str(value.get('sha256'))):
            raise RuntimeError('maintenance_original_material_missing')
        return value

    def native_accounts(self,provider):
        rows={r['Id']:r for r in provider._rows()};net=provider.contract['database']['network_name']
        endpoints={}
        for service,port in (('auth',9999),('rest',3000),('storage',5000)):
            row=rows[provider.inventory['containers']['native:'+service]['id']]
            if not row['State']['Running'] or row['State'].get('Restarting'):
                raise RuntimeError('maintenance_original_provider_not_running')
            ip=row['NetworkSettings']['Networks'][net]['IPAddress']
            endpoints[service]='http://'+ip+':'+str(port)
        storage=rows[provider.inventory['containers']['native:storage']['id']]
        return observe_subjects(self.subjects,endpoints,_env(storage)['ANON_KEY'])

    def capture_original(self,binding):
        provider=self.provider(binding,'prepare')
        if provider._database_identity()!=146:raise RuntimeError('maintenance_original_schema_required')
        observations=self.native_accounts(provider)
        result={'binding':binding,'probe_sha256':self.probe_sha256,
            'material':self.material(provider),'accounts':observations}
        self.provider(binding,'prepare')
        exclusive(self.actor.root/'original-private-acceptance.json',encoded(result))
        return result

    def acceptance(self,binding,*,private):
        if private is not True:raise RuntimeError('maintenance_private_probe_required')
        provider=self.provider(binding,'verify_native_acceptance')
        release_contract(binding).require_target_protocols(provider._database_identity(),*json.loads(provider._sql(
            'select json_build_array(public.notification_delivery_protocol(),public.notification_outbox_protocol(),public.data_deletion_ownership_protocol());')))
        from deployment.lib.schema150_provider_lifecycle import ProviderMaintenance150,ProtectedProviderJournal
        ProviderMaintenance150(binding,ProtectedProviderJournal(self.actor.root/'provider-journal'),provider)._private_boundary()
        baseline=private_json(self.actor.root/'original-private-acceptance.json')
        material=self.material(provider)
        if (baseline.get('binding')!=binding or baseline.get('probe_sha256')!=self.probe_sha256
                or baseline.get('material')!=material):
            raise RuntimeError('maintenance_original_application_changed')
        preimage=private_json(self.actor.root/'provider-journal'/'0000.json')['payload']['preimage']
        provider._object_preservation(binding,preimage)
        path=self.actor.root/'target-private-acceptance.json'
        if path.exists():
            # Independently observe an already completed probe without creating
            # another session/challenge. This is a root-owned source-produced
            # identity/material record, not an operator PASS packet.
            if private_json(path)!=baseline:raise RuntimeError('maintenance_private_acceptance_changed')
            return True
        observed={'binding':binding,'probe_sha256':self.probe_sha256,
            'material':self.material(provider),'accounts':self.native_accounts(provider)}
        if observed!=baseline:raise RuntimeError('maintenance_original_application_changed')
        self.provider(binding,'verify_native_acceptance')
        exclusive(path,encoded(observed))
        return True

    def activation(self,binding,*,private):
        if type(private) is not bool:raise RuntimeError('maintenance_activation_scope_invalid')
        provider=self.provider(binding,'observe_activation')
        schema=provider._database_identity()
        protocols=json.loads(provider._sql('select json_build_array(public.notification_delivery_protocol(),'
            'public.notification_outbox_protocol(),public.data_deletion_ownership_protocol());'))
        release_contract(binding).require_target_protocols(schema,*protocols)
        from deployment.lib.completed_normal_database import require_normal_migration_boundary,verify_migration_customer_preservation
        require_normal_migration_boundary(self.actor.contract,schema,self.actor.root,self.actor.ops.state_root)
        before=private_json(self.actor.root/'pre-migration-customer-snapshot.json')
        after=private_json(self.actor.root/'post-migration-customer-snapshot.json')
        if private_json(self.actor.root/'migration-customer-preservation.json')!=verify_migration_customer_preservation(
                before,after,contract=self.actor.contract):
            raise RuntimeError('maintenance_preservation_receipt_changed')
        original=private_json(self.actor.root/'original-private-acceptance.json')
        if (original.get('binding')!=binding or original.get('probe_sha256')!=self.probe_sha256
                or original.get('material')!=self.material(provider)):
            raise RuntimeError('maintenance_original_material_changed')
        # Root seals the actually executed restore + append-only receiver at
        # backup capture; mutable operator summaries are never inputs here.
        self.verify_backup(binding)
        from deployment.lib.completed_normal_evidence import verify_application_evidence
        verify_application_evidence(self.actor)
        observed_grant=require_candidate_authority(self.actor.contract)
        stage=provider.verify_candidate_stage(phase='active-boundary' if
            observed_grant['mode']=='NORMAL' else 'private-boundary')
        from deployment.lib.runtime_authority import load_worker_authority
        owner=load_worker_authority(self.actor.ops.state_root)
        origin=self.actor.contract['origin'];roles=self.actor.contract['source_roles']
        candidate=self.actor.contract['candidate']
        original_owner=(owner is not None and owner['owner']=='CANDIDATE'
            and owner['generation']==origin['worker_generation']
            and owner['candidate']=={'sha':roles['application_sha'],'slot':origin['slot']})
        target_owner=(owner is not None and owner['owner']=='CANDIDATE'
            and owner['generation']==stage['worker_generation']
            and owner['old']=={'sha':roles['application_sha'],'slot':origin['slot']}
            and owner['candidate']=={'sha':candidate['source_sha'],'slot':candidate['slot']})
        if not (original_owner or target_owner):raise RuntimeError('maintenance_worker_ownership_changed')
        if target_owner and observed_grant['mode']!='NORMAL':
            raise RuntimeError('maintenance_transferred_owner_requires_target_grant')
        self.actor.installation.installed();provider._verify_barrier()
        # _attest rejects unknown writers and verifies stopped origin actors,
        # exact candidate/core state, inventory and restart boundaries. Authority
        # itself is read independently after all the other observations.
        provider._attest('active-boundary' if target_owner else 'private-boundary')
        from deployment.lib.schema150_release import BACKGROUND_WRITER_SQL
        if (not provider._known_sessions(provider._sessions())
                or int(provider._sql('SELECT count(*) FROM pg_prepared_xacts;'))!=0
                or int(provider._sql('BEGIN READ ONLY;'+BACKGROUND_WRITER_SQL+';COMMIT;'))!=0):
            raise RuntimeError('maintenance_activation_unknown_writer')
        grant=require_candidate_authority(self.actor.contract)
        if grant!=observed_grant:raise RuntimeError('maintenance_activation_grant_changed')
        if grant['mode']=='NORMAL' and grant['schema']!=160:
            raise RuntimeError('maintenance_target_authority_schema_invalid')
        return {'binding_sha256':digest(binding),'schema':schema,
            'delivery_protocol':protocols[0],'outbox_protocol':protocols[1],'deletion_protocol':protocols[2],
            'target_write_authority':grant['mode']=='NORMAL',
            'write_authority_sha256':digest(grant) if grant['mode']=='NORMAL' else None,
            'migration_receipts':True,'preservation':True,'accepted_images':True,'backup_restore_replica':True,
            'worker_ownership':True,'boot_recovery':True,'private_provider_boundary':True}

    def verify_backup(self,binding):
        from scripts import backup_support
        from deployment.lib.completed_normal_migration import intent_document
        inputs=private_json(self.actor.root/'migration-inputs.json')
        receipt=private_json(self.actor.root/'pre-migration-backup.json')
        scope=digest({'operation':binding['operation'],'context_sha256':binding['context_sha256'],'backup_stage':'pre-migration'})
        restore=receipt.get('restore',{});receiver=receipt.get('node1',{})
        backup=Path(inputs.get('backup',''))
        if (inputs.get('intent')!=intent_document(self.actor.contract)
                or receipt.get('operation')!='actual-completed-normal-backup-restore-replica'
                or receipt.get('context_sha256')!=binding['context_sha256']
                or receipt.get('plan_sha256')!=scope or receipt.get('stage')!='pre-migration'
                or receipt.get('authorizing_plan_sha256')!=self.actor.contract['plan_sha256']
                or receipt.get('source_sha')!=binding['source_sha'] or receipt.get('schema')!=146
                or receipt.get('images')!=self.actor.contract['candidate']['images']
                or receipt.get('local_path')!=str(backup)
                or file_digest(readonly_configuration(backup/'manifest.json',private=False))!=inputs.get('backup_manifest_sha256')
                or file_digest(readonly_configuration(backup/'SHA256SUMS',private=False))!=inputs.get('backup_checksums_sha256')
                or receipt.get('sha256sums_sha256')!=inputs.get('backup_checksums_sha256')
                or digest(restore)!=inputs.get('restore_execution_sha256') or digest(receiver)!=inputs.get('replica_execution_sha256')
                or restore.get('status')!='logical_database_and_file_restore_passed' or restore.get('backup_schema')!=146
                or any(restore.get(k) is not True for k in ('role_attributes_restored','ownership_and_acls_restored',
                    'database_fingerprint_verified','native_object_bytes_restored'))
                or receiver.get('operation')!='actual-append-only-normal-backup-replica'
                or receiver.get('plan_sha256')!=scope or receiver.get('schema')!=146
                or receiver.get('backup_id')!=backup.name or type(receiver.get('checksum_exit_code')) is not int
                or receiver.get('checksum_exit_code')!=0
                or receiver.get('sha256sums_sha256')!=inputs.get('backup_checksums_sha256')):
            raise RuntimeError('maintenance_backup_restore_receiver_changed')
        expected=inputs.get('maintenance_manifest_sha256')
        if (not re.fullmatch('[0-9a-f]{64}',str(expected))
                or any(v.get('maintenance_manifest_sha256')!=expected for v in (receipt,restore,receiver))):
            raise RuntimeError('maintenance_backup_manifest_binding_changed')
        outer=backup_support.verify(backup)
        if (outer.get('backup_id')!=backup.name or outer.get('release',{}).get('git_sha')!=binding['source_sha']
                or str(outer.get('database',{}).get('schema_version'))!='146'):
            raise RuntimeError('maintenance_backup_release_changed')
        manifest=backup_support.verify_maintenance(backup,expected_sha256=expected)
        if manifest.get('binding')!=binding or manifest.get('schema')!=146 or manifest.get('stage')!='pre-migration':
            raise RuntimeError('maintenance_backup_original_scope_changed')
