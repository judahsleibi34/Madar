"""Independent exceptional approval in the existing release/attempt journal.

Identity, review, approval and execution remain separate. This module never
executes SQL or grants application authority. The installed root issuer verifies
its exact request under the same deployment locks as routine releases.
"""
from __future__ import annotations
import hashlib,hmac,json,os,re,time,uuid
from contextlib import contextmanager
from pathlib import Path
from .migration_inventory import canonical,digest,strict_json
from .migration_executor import atomic_json
from .provider_recovery_runtime import protected

POLICY=Path('/etc/madar/exceptional-release-policy.json')
KEY=Path('/etc/madar/release-approval.key')
CONTRACTS={'drop-independent-table-v1':'D','enable-private-table-rls-v1':'C'}
STATES={'DISCOVERED','CI_PENDING','CI_ACCEPTED','STAGING_PENDING','STAGING_ACCEPTED',
    'TECHNICAL_REVIEW_REQUIRED','AWAITING_ADMIN_APPROVAL','APPROVED','REVALIDATING',
    'AUTHORIZED_FOR_EXECUTION','EXECUTING','VERIFYING','COMPLETED','REJECTED',
    'EXPIRED','REVOKED','FAILED','RECOVERY_REQUIRED'}
EDGES={'DISCOVERED':{'CI_PENDING','FAILED'},'CI_PENDING':{'CI_ACCEPTED','FAILED'},
    'CI_ACCEPTED':{'STAGING_PENDING','FAILED'},'STAGING_PENDING':{'STAGING_ACCEPTED','FAILED'},
    'STAGING_ACCEPTED':{'TECHNICAL_REVIEW_REQUIRED','FAILED'},
    'TECHNICAL_REVIEW_REQUIRED':{'AWAITING_ADMIN_APPROVAL','FAILED'},
    'AWAITING_ADMIN_APPROVAL':{'APPROVED','REJECTED','EXPIRED','FAILED'},
    'APPROVED':{'REVALIDATING','REVOKED','EXPIRED','FAILED'},
    'REVALIDATING':{'AUTHORIZED_FOR_EXECUTION','FAILED','EXPIRED','RECOVERY_REQUIRED'},
    'AUTHORIZED_FOR_EXECUTION':{'EXECUTING','RECOVERY_REQUIRED'},
    'EXECUTING':{'VERIFYING','RECOVERY_REQUIRED'},'VERIFYING':{'COMPLETED','RECOVERY_REQUIRED'}}


def root():
    from .automatic_release_admission import ROOT
    return ROOT/'exceptional'


def identifier(value):
    try:
        if not isinstance(value,str) or str(uuid.UUID(value))!=value:raise ValueError()
    except (ValueError,TypeError,AttributeError):raise RuntimeError('exceptional_request_identity_invalid') from None
    return value


def policy(system):
    from .automatic_release_admission import execution_policy
    execution,environment=execution_policy(system)
    return _policy_material(execution,environment['database_system_identifier'])


def audit_policy(system):
    """Read authenticated journals despite a failed runtime. Never issue authority.

    The independent configuration/controller and enrolled scope remain pinned.
    All admission, approval and consumption paths still use policy(), including
    its mandatory live observation. An audit must not mask the original error.
    """
    from .automatic_release_admission import execution_policy_configuration
    from .isolated_release_environment import POLICY as environment_policy
    execution=execution_policy_configuration(system)
    environment=strict_json(protected(environment_policy,private=True).read_bytes())
    if (environment.get('version')!=2 or execution['environment_id']!='isolated-'+environment.get('realm_id','')
            or environment.get('database_system_identifier') in execution['denied_database_identifiers']):
        raise RuntimeError('exceptional_audit_enrollment_changed')
    return _policy_material(execution,environment.get('database_system_identifier'))


def _policy_material(execution,database_system_identifier):
    raw=protected(POLICY,private=True).read_bytes()
    if not 0<len(raw)<=32768:raise RuntimeError('exceptional_policy_size')
    p=strict_json(raw)
    fields={'version','policy_id','environment_id','database_system_identifier','controller_sha',
        'enabled','contracts','approval_key_sha256','max_approval_seconds','max_request_seconds',
        'max_table_bytes','max_table_rows','relation_owner','require_physical_restore','physical_recovery_receipt_sha256'}
    if (not isinstance(p,dict) or set(p)!=fields or type(p['version']) is not int or p['version']!=1
            or p['enabled'] is not True or not re.fullmatch('[a-zA-Z0-9_-]{1,128}',str(p['policy_id']))
            or p['environment_id']!=execution['environment_id']
            or p['database_system_identifier']!=database_system_identifier
            or p['controller_sha']!=execution['controller_sha']
            or not isinstance(p['contracts'],list) or not p['contracts']
            or any(c not in CONTRACTS for c in p['contracts']) or len(set(p['contracts']))!=len(p['contracts'])
            or not re.fullmatch('[a-f0-9]{64}',str(p['approval_key_sha256']))
            or not re.fullmatch('[a-f0-9]{64}',str(p['physical_recovery_receipt_sha256']))
            or p['relation_owner']!='postgres' or p['require_physical_restore'] is not True
            or any(type(p[k]) is not int or not 0<p[k]<=limit for k,limit in
                (('max_approval_seconds',300),('max_request_seconds',600),
                 ('max_table_bytes',16*1024**2),('max_table_rows',10000)))):
        raise RuntimeError('exceptional_policy_not_enrolled')
    key=protected(KEY,private=True).read_bytes()
    if not 32<=len(key)<=4096 or hashlib.sha256(key).hexdigest()!=p['approval_key_sha256']:
        raise RuntimeError('exceptional_issuer_key_changed')
    # Authentication credentials must not also be approval-signing credentials.
    from .control_plane_upgrade_authorization import RELEASE_OPERATOR_KEY
    if hmac.compare_digest(key,protected(RELEASE_OPERATOR_KEY,private=True).read_bytes()):
        raise RuntimeError('exceptional_issuer_authentication_key_reused')
    return p,key


def supported(sql,*,origin,target):
    """Exact PostgreSQL AST contract, never a Class D allowlist or regex parser."""
    from .migration_risk import analyze,_strip_locations,IDENTIFIER,CRITICAL
    from pglast import parser
    risk=analyze(sql,origin=origin,target=target)
    if not risk.transactional or not risk.schema_envelope_verified:raise RuntimeError('exceptional_sql_unsupported')
    statements=[_strip_locations(x['stmt']) for x in json.loads(parser.parse_sql_json(sql.decode()))['stmts']][2:-2]
    if len(statements)!=1:raise RuntimeError('exceptional_sql_unsupported')
    row=statements[0];contract=None;name=None
    if set(row)=={'DropStmt'}:
        v=row['DropStmt']
        if (set(v)=={'objects','removeType','behavior'} and v['removeType']=='OBJECT_TABLE'
                and v['behavior']=='DROP_RESTRICT' and len(v['objects'])==1):
            parts=v['objects'][0].get('List',{}).get('items',[])
            if len(parts)==2 and parts[0]=={'String':{'sval':'public'}}:
                name=parts[1].get('String',{}).get('sval');contract='drop-independent-table-v1'
    elif set(row)=={'AlterTableStmt'}:
        v=row['AlterTableStmt'];rel=v.get('relation',{})
        if (set(v)=={'relation','cmds','objtype'} and v['objtype']=='OBJECT_TABLE'
                and v['cmds']==[{'AlterTableCmd':{'subtype':'AT_EnableRowSecurity','behavior':'DROP_RESTRICT'}}]
                and rel=={'schemaname':'public','relname':rel.get('relname'),'inh':True,'relpersistence':'p'}):
            name=rel.get('relname');contract='enable-private-table-rls-v1'
    if (contract is None or risk.classification!=CONTRACTS[contract] or not isinstance(name,str)
            or not IDENTIFIER.fullmatch(name) or name in CRITICAL):raise RuntimeError('exceptional_sql_unsupported')
    return {'contract':contract,'schema':'public','table':name}


def inspect_contract(plan,inventory,db,p,*,locked=False):
    """A private, ordinary, dependency-free leaf table only; native observation.

    CASCADE, extensions, partitions, views, triggers, foreign keys, RLS policies,
    application grants and protocol changes are deliberately unsupported. The
    same data fingerprint is reobserved under ACCESS EXCLUSIVE before the SQL.
    """
    from psycopg import sql
    value=plan.document();rows=inventory.forward(value['origin_schema'],value['target_schema'])
    if (len(rows)!=1 or value['execution_class']!='transactional'
            or value['protected_control_plane_changed'] or value['worker_protocol_change']
            or not value['compatibility_covers_path']):raise RuntimeError('exceptional_plan_unsupported')
    operation=supported(rows[0].sql,origin=value['origin_schema'],target=value['target_schema'])
    if operation['contract'] not in p['contracts']:raise RuntimeError('exceptional_contract_not_approved_by_policy')
    name=operation['schema']+'.'+operation['table']
    if locked:db.execute(sql.SQL('LOCK TABLE {}.{} IN ACCESS EXCLUSIVE MODE').format(sql.Identifier(operation['schema']),sql.Identifier(operation['table'])))
    row=db.execute("""SELECT c.oid,pg_get_userbyid(c.relowner),c.relkind,c.relispartition,c.relrowsecurity,
        pg_total_relation_size(c.oid),c.relacl::text,
        EXISTS(SELECT 1 FROM pg_inherits WHERE inhrelid=c.oid OR inhparent=c.oid),
        EXISTS(SELECT 1 FROM pg_trigger WHERE tgrelid=c.oid AND NOT tgisinternal),
        EXISTS(SELECT 1 FROM pg_constraint WHERE (conrelid=c.oid OR confrelid=c.oid) AND contype='f'),
        EXISTS(SELECT 1 FROM pg_policy WHERE polrelid=c.oid),
        EXISTS(SELECT 1 FROM pg_depend WHERE classid='pg_class'::regclass AND objid=c.oid AND deptype='e'),
        EXISTS(SELECT 1 FROM pg_depend WHERE refclassid='pg_class'::regclass AND refobjid=c.oid
            AND classid NOT IN ('pg_class'::regclass,'pg_type'::regclass,'pg_attrdef'::regclass,'pg_constraint'::regclass))
        FROM pg_class c WHERE c.oid=to_regclass(%s)""",(name,)).fetchone()
    if (row is None or row[1]!=p['relation_owner'] or row[2]!='r' or any(row[k] for k in (3,4,7,8,9,10,11,12))
            or row[5]>p['max_table_bytes']):raise RuntimeError('exceptional_relation_not_independent_or_budget')
    # Explicit ACL entries other than the owner are forbidden, including PUBLIC.
    grants=db.execute("SELECT count(*) FROM pg_class c,LATERAL aclexplode(COALESCE(c.relacl,acldefault('r',c.relowner))) a WHERE c.oid=%s AND a.grantee<>c.relowner",(row[0],)).fetchone()[0]
    effective=db.execute("SELECT count(*) FROM pg_roles WHERE rolname<>%s AND NOT rolsuper AND (rolcanlogin OR rolname IN ('anon','authenticated','service_role')) AND has_table_privilege(oid,%s,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')",(p['relation_owner'],row[0])).fetchone()[0]
    if grants or effective:raise RuntimeError('exceptional_relation_application_grants')
    data=db.execute(sql.SQL('SELECT row_to_json(t)::text FROM {}.{} t LIMIT %s').format(sql.Identifier(operation['schema']),sql.Identifier(operation['table'])),(p['max_table_rows']+1,)).fetchall()
    if len(data)>p['max_table_rows'] or sum(len(x[0]) for x in data)>p['max_table_bytes']:
        raise RuntimeError('exceptional_relation_data_budget')
    return {**operation,'relation_oid':row[0],'owner':row[1],'table_bytes':row[5],
        'rows':len(data),'data_sha256':digest(sorted(x[0] for x in data)),'sql_sha256':rows[0].sha256,
        'maintenance':'all-original-writers-stopped-private-providers-readmitted-after-commit',
        'recovery':'independent-physical-application-v1'}


def validate_extension(value):
    x=value.get('exceptional');plan=value['plan']
    if (not isinstance(x,dict) or set(x)!={'request_id','policy_sha256','contract','writer_inventory_sha256'}
            or any(not re.fullmatch('[a-f0-9]{64}',str(x[k])) for k in ('policy_sha256','writer_inventory_sha256'))
            or not isinstance(x['contract'],dict) or x['contract'].get('contract') not in CONTRACTS
            or plan.get('risk_class')!=CONTRACTS[x['contract']['contract']]
            or len(plan.get('migrations',[]))!=1 or value.get('environment')!='isolated-test'):
        raise RuntimeError('exceptional_admission_scope_invalid')
    identifier(x['request_id']);return x


def _signature(body,key):return hmac.new(key,canonical(body),hashlib.sha256).hexdigest()


def sign(body,key):return {'payload':body,'signature':_signature(body,key)}


def verified(path,key):
    raw=protected(path,private=True).read_bytes()
    if len(raw)>4*1024**2:raise RuntimeError('exceptional_record_budget')
    record=strict_json(raw)
    if (not isinstance(record,dict) or set(record)!={'payload','signature'}
            or not isinstance(record['signature'],str)
            or not hmac.compare_digest(record['signature'],_signature(record['payload'],key))):
        raise RuntimeError('exceptional_signature_invalid')
    return record['payload']


@contextmanager
def journal_lock(request_id):
    from .control_plane_upgrade import acquire_lock,require_root_directory
    from .automatic_release_admission import ROOT
    identifier(request_id);require_root_directory(ROOT,create=True);require_root_directory(root(),create=True)
    path=root()/request_id;require_root_directory(path,create=True)
    # Persist new request and journal namespace entries, not just their files.
    for parent in (ROOT.parent,ROOT,root()):
        directory=os.open(parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:os.fsync(directory)
        finally:os.close(directory)
    fd=acquire_lock(path/'approval.lock',create=True)
    try:yield path
    finally:os.close(fd)


def history(path,key):
    entries=[];previous=None
    for n,p in enumerate(sorted(path.glob('event-*.json'))):
        if p.name!='event-'+str(n).zfill(6)+'.json':raise RuntimeError('exceptional_audit_sequence_changed')
        value=verified(p,key)
        if value['sequence']!=n or value['previous_sha256']!=previous:raise RuntimeError('exceptional_audit_chain_changed')
        previous=digest(value);entries.append(value)
    return entries


def event(path,key,state,detail):
    entries=history(path,key);old=entries[-1]['state'] if entries else None
    if state not in STATES or (old is None and state!='DISCOVERED') or (old is not None and state not in EDGES.get(old,set())):
        raise RuntimeError('exceptional_state_transition_invalid')
    value={'sequence':len(entries),'previous_sha256':digest(entries[-1]) if entries else None,
        'state':state,'at':int(time.time()),'detail':detail}
    atomic_json(path/('event-'+str(len(entries)).zfill(6)+'.json'),sign(value,key),exclusive=True)
    return value


def _request(path,key):
    value=verified(path/'request.json',key)
    if value['request_id']!=path.name or digest(value['admission'])!=value['admission_sha256']:
        raise RuntimeError('exceptional_request_binding_changed')
    return value


def create(system,source):
    """Import independently executed CI/staging evidence, never manufacture it."""
    from .automatic_release_admission import observe_admission,publish,require_no_pending_operation
    p,key=policy(system);require_no_pending_operation();request_id=str(uuid.uuid4())
    with journal_lock(request_id) as path:
        event(path,key,'DISCOVERED',{'source_sha':source,'requested_by':'controller:'+system.installed_sha()})
        event(path,key,'CI_PENDING',{'source_sha':source})
        try:
            value=observe_admission(system,source,exceptional_request_id=request_id)
            publish(value)
            from .automatic_release_admission import execution_policy,independent_evidence
            execution,_=execution_policy(system)
            acceptance=independent_evidence(source,execution)
            if (acceptance['attempt_id']!=value['attempt_id'] or acceptance['images']!=value['candidate']['images']
                    or any(digest(acceptance['gates'][k])!=value['evidence'][k] for k in acceptance['gates'])):
                raise RuntimeError('exceptional_review_evidence_changed')
            proof_expires=value['expires_at']
            tree=system.root_git('exceptional_review_tree','rev-parse',source+'^{tree}',cwd=system.repo).stdout.strip()
            if not re.fullmatch('[a-f0-9]{40}',tree):raise RuntimeError('exceptional_source_tree_invalid')
            request={'version':1,'source_tree_sha':tree,'authenticated_acceptance':acceptance,'request_id':request_id,'admission_sha256':digest(value),'admission':value,
                'policy_sha256':digest(p),'created_at':int(time.time()),'expires_at':min(proof_expires,int(time.time())+p['max_request_seconds']),
                'review':{'why':'Independent approval required for '+value['plan']['risk_class']+' '+value['exceptional']['contract']['contract'],
                    'impact':value['exceptional']['contract'],'backup_and_recovery':acceptance['gates']['recovery'],
                    'independent_physical_receipt_sha256':p['physical_recovery_receipt_sha256'],
                    'ci':acceptance['gates']['ci'],'staging':acceptance['gates']['staging'],
                    'artifacts':acceptance['gates']['artifacts'],
                    'sql':[{k:r[k] for k in ('path','sha256','risk','from_schema','to_schema')} for r in value['plan']['migrations']],
                    'maintenance':'Write ingress and original writers unavailable until private target and exclusive workers pass acceptance.',
                    'recovery_limitations':'Committed SQL is forward-only; uncertainty preserves maintenance fencing. Approval cannot authorize replay.'}}
            atomic_json(path/'request.json',sign(request,key),exclusive=True)
            for state in ('CI_ACCEPTED','STAGING_PENDING','STAGING_ACCEPTED','TECHNICAL_REVIEW_REQUIRED','AWAITING_ADMIN_APPROVAL'):
                event(path,key,state,{'admission_sha256':digest(value),'evidence':value['evidence']})
            return {'request_id':request_id,'request_sha256':digest(request),'state':'AWAITING_ADMIN_APPROVAL','review':request['review']}
        except Exception as error:
            event(path,key,'FAILED',{'error_type':type(error).__name__})
            raise


def inspect(system,request_id):
    _,key=audit_policy(system)
    with journal_lock(request_id) as path:
        entries=history(path,key)
        if not entries:raise RuntimeError('exceptional_request_unknown')
        state=entries[-1]['state']
        if not (path/'request.json').exists():
            return {'request':None,'request_id':request_id,'request_sha256':None,'state':state,'approval':None,'consumed':False,'audit':entries}
        request=_request(path,key)
        approval=verified(path/'approval.json',key) if (path/'approval.json').exists() else None
        if state in {'APPROVED','AWAITING_ADMIN_APPROVAL'} and min(request['expires_at'],(approval or {}).get('expires_at',request['expires_at']))<=int(time.time()):state='EXPIRED'
        consumed=(path/'approval-consumed.json').exists()
        if consumed:
            owner=verified(path/'approval-consumed.json',key)
            if state in {'REVALIDATING','AUTHORIZED_FOR_EXECUTION','EXECUTING','VERIFYING'}:
                try:
                    process=Path('/proc')/str(owner['pid'])
                    live=(owner['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip()
                        and process.stat().st_uid==0
                        and process.joinpath('stat').read_text().split(') ',1)[1].split()[19]==owner['process_start'])
                except (FileNotFoundError,ProcessLookupError,KeyError,IndexError):live=False
                if not live:state='RECOVERY_REQUIRED'
        return {'request':request,'request_sha256':digest(request),'state':state,
            'approval':approval,'consumed':consumed,'audit':entries}


def decide(system,request_id,action,token,confirmation):
    if action not in {'approve','reject','revoke'}:raise RuntimeError('exceptional_operator_action_invalid')
    p,key=policy(system);operator=system.authenticate_operator(token)
    with journal_lock(request_id) as path:
        request=_request(path,key);entries=history(path,key);state=entries[-1]['state'];now=int(time.time())
        if confirmation!=digest(request):raise RuntimeError('exceptional_explicit_confirmation_required')
        if request['policy_sha256']!=digest(p):raise RuntimeError('exceptional_policy_changed')
        if request['expires_at']<=now:
            if state in {'APPROVED','AWAITING_ADMIN_APPROVAL'}:event(path,key,'EXPIRED',{'request_sha256':digest(request)})
            raise RuntimeError('exceptional_request_expired')
        if (path/'approval-consumed.json').exists():raise RuntimeError('exceptional_approval_consumed')
        if action=='revoke':
            if state!='APPROVED':raise RuntimeError('exceptional_approval_not_revocable')
            atomic_json(path/'revoked.json',sign({'operator':operator,'request_sha256':digest(request),'revoked_at':now},key),exclusive=True)
            event(path,key,'REVOKED',{'operator':operator,'request_sha256':digest(request)})
        elif state!='AWAITING_ADMIN_APPROVAL':raise RuntimeError('exceptional_request_not_pending')
        elif action=='reject':event(path,key,'REJECTED',{'operator':operator,'request_sha256':digest(request)})
        else:
            # Deliberate approval revalidates exact artifacts/state as well as identity.
            observed=system.reobserve_automatic_admission(request['admission'])
            if observed!=request['admission']:raise RuntimeError('exceptional_technical_observation_changed')
            approval={'version':1,'approval_id':str(uuid.uuid4()),'request_sha256':digest(request),
                'admission_sha256':request['admission_sha256'],'policy_sha256':digest(p),
                'operator':operator,'issuer':'installed-root-release-issuer','issued_at':now,
                'expires_at':min(request['expires_at'],request['admission']['expires_at'],now+p['max_approval_seconds'])}
            atomic_json(path/'approval.json',sign(approval,key),exclusive=True)
            event(path,key,'APPROVED',{'approval_sha256':digest(approval),'operator':operator})
        return {'request_id':request_id,'state':history(path,key)[-1]['state']}


def verify_execution(value,system,*,consume=False,token=None):
    """Called with both deployment locks, including on issuer credential creation."""
    from .schema150_provider_adapter import require_owned_lock
    require_owned_lock(system.automatic_upgrade_lock,system.upgrade_root/'upgrade.lock')
    require_owned_lock(system.deploy_lock_descriptor,system.state_root/'deploy.lock')
    x=validate_extension(value);p,key=policy(system)
    with journal_lock(x['request_id']) as path:
        request=_request(path,key);approval=verified(path/'approval.json',key)
        state=history(path,key)[-1]['state'];now=int(time.time())
        if (request['admission']!=value or request['policy_sha256']!=digest(p)
                or x['policy_sha256']!=digest(p) or approval['policy_sha256']!=digest(p)
                or approval['request_sha256']!=digest(request) or approval['admission_sha256']!=digest(value)
                or not approval['issued_at']<approval['expires_at']<=min(request['expires_at'],value['expires_at'],approval['issued_at']+p['max_approval_seconds'])):
            raise RuntimeError('exceptional_approval_scope_changed')
        if min(request['expires_at'],approval['expires_at'])<=now:
            if state=='APPROVED':event(path,key,'EXPIRED',{'approval_sha256':digest(approval)})
            raise RuntimeError('exceptional_approval_expired')
        if (path/'revoked.json').exists():
            verified(path/'revoked.json',key)
            raise RuntimeError('exceptional_approval_revoked')
        consumed=path/'approval-consumed.json'
        owner={'admission_sha256':digest(value),'approval_sha256':digest(approval),'attempt_id':value['attempt_id'],
            'pid':os.getpid(),'process_start':Path('/proc/self/stat').read_text().split(') ',1)[1].split()[19],
            'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
        if consume:
            if consumed.exists():raise RuntimeError('exceptional_approval_consumed')
            if state!='APPROVED':raise RuntimeError('exceptional_approval_not_executable')
            observed=system.reobserve_automatic_admission(value)
            if observed!=value:raise RuntimeError('exceptional_technical_observation_changed')
            from .automatic_release_migration import prepared
            prepared(value,system)
            operator=system.authenticate_operator(token)
            if any(operator[k]!=approval['operator'][k] for k in ('operator_auth_id','policy_sha256','session_id_sha256')):
                raise RuntimeError('exceptional_current_operator_changed')
            event(path,key,'REVALIDATING',{'operator':operator})
            atomic_json(consumed,sign(owner,key),exclusive=True)
            event(path,key,'AUTHORIZED_FOR_EXECUTION',{'consumption_sha256':digest(owner)})
        elif (not consumed.exists() or verified(consumed,key)!=owner
                or state not in {'AUTHORIZED_FOR_EXECUTION','EXECUTING','VERIFYING'}):
            raise RuntimeError('exceptional_approval_not_owned_or_revoked')
        return approval


def execution_event(system,value,state,detail):
    p,key=audit_policy(system)
    if digest(p)!=validate_extension(value)['policy_sha256']:
        raise RuntimeError('exceptional_policy_changed')
    with journal_lock(validate_extension(value)['request_id']) as path:
        if _request(path,key)['admission']!=value:
            raise RuntimeError('exceptional_audit_admission_changed')
        return event(path,key,state,detail)


def verify_independent_recovery(p,execution,proof,*,now):
    from .automatic_release_admission import physical_recovery_evidence,PHYSICAL_RECOVERY
    raw=protected(PHYSICAL_RECOVERY/(p['physical_recovery_receipt_sha256']+'.json'),private=True).read_bytes()
    trust=strict_json(raw)
    if trust.get('database_system_identifier')!=p['database_system_identifier']:
        raise RuntimeError('exceptional_recovery_database_changed')
    evidence={'kind':'independent-physical-application-v1',
        'source_system_identifier':p['database_system_identifier'],'restore_system_identifier':p['database_system_identifier'],
        'restored_schema':trust.get('schema'),'receipt_sha256':p['physical_recovery_receipt_sha256']}
    physical_recovery_evidence(evidence,execution,proof['history_base_sha'],proof['gates']['compatibility']['protocols'],now=now)
    if trust['schema']!=proof['gates']['recovery']['restored_schema']:
        raise RuntimeError('exceptional_recovery_origin_changed')
