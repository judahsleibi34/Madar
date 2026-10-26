"""Generic source-bound release preparation. Plans contain no execution authority.

Historical completed-NORMAL profiles are unchanged. This representation does
not register a new production executor. Live provenance, compatibility, drift,
recovery and independently protected admission remain mandatory.
"""
from __future__ import annotations
from dataclasses import dataclass
import json
from fnmatch import fnmatchcase
from .migration_inventory import GitSource, Inventory, canonical, digest, strict_json
from .migration_risk import RANK, analyze, measured_operations
from .schema148_artifacts import INPUTS as ARTIFACT_INPUTS

INTENT_PATH = 'web/database/migration-intent.json'
PROTOCOLS = {'delivery', 'outbox', 'deletion'}
# Root policy pins this preparation/build trust root independently of the PR's
# moving base. Source-controlled CI success cannot approve its own verifier.
AUTOMATION_INPUTS=tuple(dict.fromkeys((*ARTIFACT_INPUTS,
    '.github/workflows/backend-check.yml','.github/workflows/frontend-check.yml',
    '.github/workflows/schema148-artifacts.yml','.github/workflows/migration-safety.yml',
    'web/backend/Dockerfile','web/frontend/Dockerfile','web/backend/requirements-migration-tools.txt',
    'web/backend/scripts/run_tests_no_external_network.py','web/backend/scripts/verify_installed_constraints.py',
    'web/frontend/vite.config.js','web/frontend/private-provider160.conf',
    'web/scripts/build_schema148_artifacts.py','web/scripts/check_dependency_locks.py',
    'web/scripts/check_migrations.py','web/scripts/check_migration_transitions.py',
    'web/scripts/check_forward_release.py','web/scripts/validate_migration_candidate.py',
    'web/scripts/rehearse_generic_migrations.sh','web/scripts/rehearse_migration_candidate.py',
    'web/scripts/rehearse_migration_policy.sh','web/backend/tests/test_migration_policy_filesystem.py',
    'web/deployment/lib/migration_inventory.py','web/deployment/lib/migration_risk.py',
    'web/deployment/lib/migration_plan.py','web/deployment/lib/migration_policy.py',
    'web/deployment/lib/migration_executor.py','web/deployment/lib/migration_drift.py',
    'web/deployment/lib/schema148_artifacts.py')))


def automation_inputs(git,source):
    import hashlib
    # Include dependency trees, not just known entrypoints: an approved workflow
    # may import a newly introduced helper without changing its own bytes. A
    # moving Git base cannot enroll that helper into an independent root policy.
    files=git.files(source,*AUTOMATION_INPUTS,'.github/workflows/','.github/actions/',
        'web/deployment/','web/scripts/','web/staging/integration/',
        'web/backend/scripts/','web/frontend/scripts/',allow_executable=True)
    missing=sorted(set(AUTOMATION_INPUTS)-set(files))
    hashes={path:{'sha256':hashlib.sha256(body).hexdigest(),'mode':git.modes[(source,path)]}
            for path,body in sorted(files.items())}
    return {'files':hashes,'missing':missing,'sha256':digest({'files':hashes,'missing':missing})}



def compatibility_intent(git, source):
    files=git.files(source, INTENT_PATH)
    if not files: return None
    body=files[INTENT_PATH]
    if len(body)>32768: raise RuntimeError('migration_intent_size_limit')
    value=strict_json(body)
    required={'version','compatible_min','compatible_max','rolling_compatible','worker_protocols','declared_class'}
    if (not isinstance(value,dict) or set(value)!=required or type(value['version']) is not int or value['version']!=1
            or type(value['compatible_min']) is not int or type(value['compatible_max']) is not int
            or not 0<value['compatible_min']<=value['compatible_max']<10**9
            or type(value['rolling_compatible']) is not bool or value['declared_class'] not in RANK
            or not isinstance(value['worker_protocols'],dict) or set(value['worker_protocols'])!=PROTOCOLS
            or any(type(v) is not int or not 0<v<1000 for v in value['worker_protocols'].values())):
        raise RuntimeError('migration_intent_invalid')
    return value


def release_change_risk(git,base,source):
    """Whole-release risk from installed code rules, not candidate declarations.

    App-only is not synonymous with safe: changing authorization, worker
    ownership, storage contracts or verifiers requires coordinated review even
    without SQL. Root policy independently pins this analyzer and its imports.
    """
    paths=sorted(p.decode('utf-8') for p in git.command('diff','--no-ext-diff','--no-textconv',
        '--name-only','-z',base,source,'--').split(b'\0') if p)
    critical_services=('auth','mfa','tenant','identity','access','security','entitlement','billing','payment',
        'storage','provider_recovery','business_write_authority','notification','outbox','deletion',
        'external_effect','calendar','reservation','inventory','order','cache','remote_ingestion')
    from .control_plane_upgrade import PROTECTED_PATHS
    groups={'control_plane':[],'verification':[],'authorization_and_data_contract':[],'worker_contract':[]}
    for path in paths:
        if any(path==root or path.startswith(root+'/') for root in PROTECTED_PATHS):groups['control_plane'].append(path)
        if path.startswith(('.github/','web/backend/scripts/','web/frontend/scripts/','web/staging/integration/')):
            groups['verification'].append(path)
        if (path in {'web/backend/app.py','web/backend/database.py'} or path.startswith('web/backend/routes/')
                or any(fnmatchcase(path,'web/backend/services/*'+word+'*.py') for word in critical_services)):
            groups['authorization_and_data_contract'].append(path)
        if path.startswith('web/backend/workers/'):groups['worker_contract'].append(path)
    return {'class':'C' if any(groups.values()) else 'A','changed_paths_sha256':digest(paths),
            'review_sensitive_paths':groups}


@dataclass(frozen=True)
class ReleasePlan:
    encoded: bytes

    @property
    def sha256(self):
        import hashlib
        return hashlib.sha256(self.encoded).hexdigest()

    def document(self): return strict_json(self.encoded)


def generate(root, inventory: Inventory, *, origin, target=None):
    # Inventory is produced from immutable Git objects by discover(). Root
    # consumers must rediscover, never deserialize a caller-supplied Inventory.
    path=inventory.forward(origin,target)
    target=origin if not path else path[-1].number
    git=GitSource(root)
    intent=compatibility_intent(git,inventory.source_sha)
    automation=automation_inputs(git,inventory.source_sha)
    previous_intent=compatibility_intent(git,inventory.history_base_sha)
    protocol_change=bool(intent and (not previous_intent or intent['worker_protocols']!=previous_intent['worker_protocols']))
    # Use the existing control-plane guard's actual protected-path contract.
    from .control_plane_upgrade import PROTECTED_PATHS
    changed=git.command('diff','--no-ext-diff','--no-textconv','--name-only',inventory.history_base_sha,inventory.source_sha,'--',*PROTECTED_PATHS)
    control_plane_changed=bool(changed.strip())
    changes=release_change_risk(git,inventory.history_base_sha,inventory.source_sha)
    rows=[]; previous=origin; classification='A'
    for migration in path:
        risk=analyze(migration.sql,origin=previous,target=migration.number)
        if RANK[risk.classification]>RANK[classification]: classification=risk.classification
        rows.append({**migration.record(),'from_schema':previous,'to_schema':migration.number,'risk':risk.document(),
            'measurable_operations':measured_operations(migration.sql,origin=previous,target=migration.number)})
        previous=migration.number
    if intent and RANK[intent['declared_class']]>RANK[classification]: classification=intent['declared_class']
    if RANK[changes['class']]>RANK[classification]:classification=changes['class']
    if protocol_change and RANK[classification]<RANK['C']: classification='C'
    if intent and not intent['rolling_compatible'] and RANK[classification]<RANK['C']: classification='C'
    compatible=bool(intent and intent['compatible_min']<=origin<=target<=intent['compatible_max'])
    gates=['exact_source','protected_integration','authenticated_images','staging_acceptance',
           'application_compatibility','worker_compatibility','database_identity','schema_and_history_drift',
           'controller_identity','deployment_lock','trusted_automation_inputs','fresh_independent_authority']
    if path: gates+=['native_migration_rehearsal','backup_integrity','restore_acceptance','resource_and_lock_budget']
    if classification=='B': gates+=['live_size_and_lock_review']
    if classification=='C': gates+=['protected_maintenance','provider_and_worker_quiescence','private_acceptance','forward_repair']
    if classification=='D': gates+=['exceptional_reviewed_operation_contract']
    if control_plane_changed: gates+=['protected_control_plane_upgrade']
    value={'version':1,'kind':'migration' if path else 'application-only',
        'repository':'judahsleibi34/Madar','source_sha':inventory.source_sha,
        'history_base_sha':inventory.history_base_sha,'inventory_sha256':digest(inventory.document()),
        'origin_schema':origin,'target_schema':target,'migrations':rows,'risk_class':classification,
        'automation_inputs':automation,
        'compatibility_intent':intent,'compatibility_covers_path':compatible,'worker_protocol_change':protocol_change,
        'protected_control_plane_changed':control_plane_changed,
        'release_change_risk':changes,
        'execution_class':'transactional' if all(row['risk']['transactional'] for row in rows) else 'unsupported',
        'required_gates':sorted(gates),'backup_policy':'verified-current-data-and-original-roles' if path else 'policy-dependent',
        'recovery_policy':'observe-commit-then-protected-forward-repair' if path else 'runtime-compatibility-dependent',
        'artifact_provenance':{'status':'PENDING','required_source_sha':inventory.source_sha},
        'production_controller_integration':'BLOCKED','authority_issued':False}
    value['operation_id']='migration-plan-'+digest(value)
    return ReleasePlan(canonical(value))


def verify(root, inventory, *, encoded):
    if type(encoded) is not bytes or len(encoded)>4*1024*1024: raise RuntimeError('migration_plan_size_or_type_invalid')
    value=strict_json(encoded)
    expected=generate(root,inventory,origin=value['origin_schema'],target=value['target_schema'])
    if encoded!=expected.encoded: raise RuntimeError('migration_plan_source_or_metadata_substitution')
    return expected
