"""Exact canonical146→160 inputs and observations for the existing controller.

Preparation is not admission. Neither old146→150 credentials nor a matching
numeric schema can authorize this operation. The operational registry remains
closed pending full privileged preserved-application acceptance.
"""
from pathlib import Path

from deployment.lib.schema150_release import (
    COUNTERS, QUIESCENCE_SQL as HISTORICAL_QUIESCENCE_SQL, captured_json,
    _captured_sql, _observe_database_quiescence,
)

MANIFEST = 'migrations-147-160-coordinated.json'
BRIDGE = 'schema-146-160-coordinated.json'
MANIFEST_SHA256 = '7633a15a9f531874409577fb9696e472631d3bbde63ae2603be0a4d23ef7c08f'
BRIDGE_SHA256 = '6e5ef995507f3edc421d9e2731b0fd87069160226756df2bcdc04004a6e13456'
SCHEMAS = tuple(range(146, 161))
SQL_CONTRACT = {
    147: ('3abf6867a6fb41049334690423ac0375af39fdfd8b91196874e6e1857c2aa8fb', 'expand-only'),
    148: ('c145733bde3ae4a67a07159e0574247146bbe3fcc0ba670eee4207c5fa67e6da', 'expand-only'),
    149: ('8be053ce38ab3ac25a5874976a54ec1446d6e8ee5838c8e69fe4d835dd7ec370', 'expand-only'),
    150: ('cc0489553fcbf34475aa5d208039305da1180d0118cf4d77ab3c9575c1b1dddb', 'expand-only'),
    151: ('8fca93aed099388b94ec9a3073d00bf435a717259141e9fa6450ca7513952c14', 'expand-only'),
    152: ('60f98341ef12098a924deea208528e853020cb188509356a6ede32b322bce04f', 'expand-only'),
    153: ('02e2f6b866d4f8ea1807ab5d181e6a327040f035e2e06aa8c13e74cad872f9c8', 'expand-only'),
    154: ('3ef4c0417bf5bed8898a58eceb877b4be32bc3c29c675dd6baee43a2834e0d33', 'expand-only'),
    155: ('451df6fd773155f43c6db456987b222df33d70a20300776cf7fee4f8c586372e', 'expand-only'),
    156: ('b09b23c2e968cc2ad1f3d4a89a6f060e9038e1d3c70687405c9d54a4eee6111b', 'expand-only'),
    157: ('52476307bff528438bad4605ffcf1dace7e4b2bbf5a27c44bded591e24d978de', 'coordinated'),
    158: ('4cb81048a81efe58ccf662ee9219e2c1f84d64f697695e89db0871cbbd7735c1', 'forward-compatible'),
    159: ('bde2aff049fe3813398926b95dd8082acf5e9cda755b3ac9eb362d99ded392ca', 'coordinated'),
    160: ('26047edda49f11d7fd3100f3c8a665d332983d6d806a32a10ea48a55b62b9de2', 'coordinated'),
}
# At canonical150..159 deletion is still legacy. A pending request must block
# maintenance until reconciled; the archived150 threshold is unsafe here.
QUIESCENCE_SQL = HISTORICAL_QUIESCENCE_SQL.replace('<150', '<160')


def captured_source(root):
    """Capture the fourteen immutable active migrations, never archived SQL."""
    root = Path(root).resolve()
    raw = captured_json(root/'web/deployment/releases'/MANIFEST, MANIFEST_SHA256)
    bridge = captured_json(root/'web/deployment/releases'/BRIDGE, BRIDGE_SHA256)
    if (bridge['schema'] != {'compatible_min': 146, 'compatible_max': 160, 'target': 160,
            'migration_class': 'coordinated', 'rollback_compatible_min': 160,
            'rollback_compatible_max': 160}
            or bridge['migration_manifest'] != MANIFEST or bridge['migration_policy'] != 'none'
            or raw.get('execution_status') != 'blocked_pending_protected_controller_acceptance'
            or [r['number'] for r in raw['migrations']] != list(range(147, 161))):
        raise RuntimeError('schema160_chain_invalid')
    snapshots = {}
    for row in raw['migrations']:
        number = row['number']
        path = Path(row['path'])
        if (type(number) is not int or row['from_schema'] != number-1 or row['to_schema'] != number
                or path.parent.as_posix() != 'web/database/migrations'
                or not path.name.startswith(str(number)+'_') or path.suffix != '.sql'
                or (row['sha256'], row['compatibility']) != SQL_CONTRACT[number]):
            raise RuntimeError('schema160_chain_invalid')
        mirror = Path('web/supabase/migrations')/path.name
        for relative in (path, mirror):
            if any((root/p).is_symlink() for p in relative.parents if p != Path('.')):
                raise RuntimeError('schema160_sql_path_invalid')
        body = _captured_sql(root/path, row['sha256'])
        if body != _captured_sql(root/mirror, row['sha256']):
            raise RuntimeError('schema160_sql_mirror_changed')
        snapshots[number] = body
    return raw, snapshots


ISOLATED_REGISTRATION=Path('/etc/madar/schema160-isolated-acceptance.json')


def require_independent_recovery(document,contract,system):
    """Use the existing physical receiver verifier for this enrolled origin.

    This is a technical precondition, not approval or migration authority. The
    immutable plan names a root-enrolled receiver receipt; no caller boolean can
    stand in for full independently signed restored-application acceptance.
    """
    import re,time
    from .automatic_release_admission import execution_policy,physical_recovery_evidence
    evidence=document.get('independent_recovery')
    if (not isinstance(evidence,dict) or set(evidence)!={'receipt_sha256'}
            or not re.fullmatch('[a-f0-9]{64}',str(evidence['receipt_sha256']))):
        raise RuntimeError('schema160_independent_recovery_receipt_required')
    policy,environment=execution_policy(system)
    if (policy['controller_sha']!=contract['candidate']['controller_sha']
            or environment['database_system_identifier']!=contract['database']['system_identifier']):
        raise RuntimeError('schema160_independent_recovery_scope_changed')
    recovery={'kind':'independent-physical-application-v1',
        'source_system_identifier':contract['database']['system_identifier'],
        'restore_system_identifier':contract['database']['system_identifier'],
        'restored_schema':146,'receipt_sha256':evidence['receipt_sha256']}
    physical_recovery_evidence(recovery,policy,contract['source_roles']['application_sha'],
        {'delivery':1,'outbox':1,'deletion':0},now=int(time.time()),historical_binding=contract['source_roles'])
    return recovery


def isolated_registration(contract):
    """Independently pinned technical profile; never SQL/deployment authority.

    The ordinary registry stays closed. Only a positively identified disposable
    KVM guest may recognize the exact frozen first-rehearsal context. A candidate
    cannot write this root-owned policy. Every privileged effect still requires
    the existing issuer credential and independent exceptional approval.
    """
    import os,re,time
    from .provider_recovery_runtime import protected
    from .migration_inventory import strict_json
    from .completed_normal_admission import digest
    from .completed_normal_profile import RECONCILED
    from .historical_origin import KIND,validate_source_binding
    path=protected(ISOLATED_REGISTRATION)
    metadata=path.stat()
    if metadata.st_mode&0o222 or not 0<metadata.st_size<=8192:
        raise RuntimeError('schema160_isolated_registration_not_frozen')
    p=strict_json(path.read_bytes())
    fields={'version','kind','environment_id','guest_uuid','machine_id','root_filesystem_uuid',
        'operation','context_sha256','plan_sha256','controller_sha','application_sha',
        'database_system_identifier','origin_schema','target_schema','created_at','expires_at'}
    if (not isinstance(p,dict) or set(p)!=fields or type(p.get('version')) is not int or p['version']!=1
            or p['kind']!='isolated-canonical-controller-acceptance'
            or contract.get('operation')!=RECONCILED.operation or contract.get('version')!=RECONCILED.version
            or contract.get('source_roles',{}).get('origin_kind')!=KIND
            or p['operation']!=RECONCILED.operation or p['context_sha256']!=digest(contract)
            or p['plan_sha256']!=contract.get('plan_sha256')
            or p['controller_sha']!=contract.get('candidate',{}).get('controller_sha')
            or p['application_sha']!=contract.get('candidate',{}).get('source_sha')
            or p['database_system_identifier']!=contract.get('database',{}).get('system_identifier')
            or type(p['origin_schema']) is not int or p['origin_schema']!=146
            or type(p['target_schema']) is not int or p['target_schema']!=160
            or any(not re.fullmatch('[a-f0-9]{64}',str(p[k])) for k in ('context_sha256','plan_sha256'))
            or any(not re.fullmatch('[a-f0-9]{40}',str(p[k])) for k in ('controller_sha','application_sha'))
            or type(p['created_at']) is not int or type(p['expires_at']) is not int
            or not p['created_at']<=int(time.time())<p['expires_at']<=p['created_at']+10800):
        raise RuntimeError('schema160_isolated_registration_scope_invalid')
    validate_source_binding(contract['source_roles'])
    from .isolated_release_environment import observe_host,observe_effect_fence,run
    if os.geteuid()==0:
        host=observe_host();observe_effect_fence(execution=True)
        if (host['version']!=2 or p['environment_id']!='isolated-'+host['realm_id']
                or host['database_system_identifier']!=p['database_system_identifier']
                or p['database_system_identifier'] in host['denied_database_identifiers']
                or any(p[k]!=host[k] for k in ('guest_uuid','machine_id','root_filesystem_uuid'))):
            raise RuntimeError('schema160_isolated_registration_host_changed')
    else:
        # A child receives only the existing fresh, context-scoped credential;
        # root-private environment policy is never exposed to the child.
        from .control_plane_upgrade_authorization import require_upgrade_authorization
        require_upgrade_authorization(p['controller_sha'],required_operation=RECONCILED.operation,
            required_schema=146,required_context_digest=digest(contract),require_rehearsal=True)
        if (Path('/sys/class/dmi/id/product_uuid').read_text().strip().lower()!=p['guest_uuid']
                or Path('/etc/machine-id').read_text().strip()!=p['machine_id']
                or run(['/usr/bin/systemd-detect-virt']).decode().strip()!='kvm'
                or run(['/usr/bin/findmnt','-n','-o','UUID','/']).decode().strip()!=p['root_filesystem_uuid']):
            raise RuntimeError('schema160_isolated_registration_host_changed')
    return p


def admitted_manifest(root, contract):
    try:isolated_registration(contract)
    except (OSError,RuntimeError,ValueError):
        raise RuntimeError('schema160_protected_controller_integration_incomplete') from None
    from .completed_normal_profile import RECONCILED
    from .control_plane_upgrade_authorization import require_upgrade_authorization
    from .migration_executor import MigrationManifest,Migration
    from .completed_normal_admission import digest
    require_upgrade_authorization(contract['candidate']['controller_sha'],required_operation=RECONCILED.operation,
        required_schema=146,required_context_digest=digest(contract),require_rehearsal=True)
    raw,_=captured_source(root)
    if contract['migration_manifest_sha256']!=MANIFEST_SHA256:
        raise RuntimeError('schema160_migration_manifest_changed')
    return MigrationManifest(release_sha=contract['candidate']['source_sha'],coordinated=True,
        migrations=tuple(Migration(number=r['number'],path=Path(root)/r['path'],sha256=r['sha256'],
            from_schema=r['from_schema'],to_schema=r['to_schema'],compatibility=r['compatibility']) for r in raw['migrations']))


def expected_protocols(schema):
    if type(schema) is not int or schema not in SCHEMAS:
        raise RuntimeError('schema160_database_schema_invalid')
    return {'delivery_protocol': 2 if schema >= 157 else 1,
            'outbox_protocol': 2 if schema >= 159 else 1,
            'deletion_protocol': 2 if schema == 160 else 0}


def require_database_quiescence(observed, contract, expected_schema):
    protocols = expected_protocols(expected_schema)
    if (not isinstance(observed, dict) or set(observed) != {'system_identifier', 'schema', *protocols, *COUNTERS}
            or observed['system_identifier'] != contract['database']['system_identifier']
            or type(observed['schema']) is not int or observed['schema'] != expected_schema
            or any(type(observed[k]) is not int or observed[k] != v for k, v in protocols.items())
            or any(type(observed[k]) is not int or observed[k] != 0 for k in COUNTERS)):
        raise RuntimeError('schema160_database_not_quiescent')
    return observed


def observe_database_quiescence(cursor, contract, expected_schema):
    protocols = expected_protocols(expected_schema)
    observed = _observe_database_quiescence(cursor, QUIESCENCE_SQL, (
        ('delivery_protocol', 'notification_delivery_protocol', protocols['delivery_protocol'] == 2),
        ('outbox_protocol', 'notification_outbox_protocol', protocols['outbox_protocol'] == 2),
        ('deletion_protocol', 'data_deletion_ownership_protocol', protocols['deletion_protocol'] == 2)))
    return require_database_quiescence(observed, contract, expected_schema)


def observation_sql(schema):
    """Fixed native psql transport for the same canonical protocol checks."""
    protocols = expected_protocols(schema)
    functions = (('delivery_protocol', 'notification_delivery_protocol'),
                 ('outbox_protocol', 'notification_outbox_protocol'),
                 ('deletion_protocol', 'data_deletion_ownership_protocol'))
    fields = []
    for key, function in functions:
        if protocols[key] == 2:
            expression = 'public.'+function+'()'
        else:
            # An unexpected early function is a divergent history, even if it
            # returns a convenient legacy number. No absent function is parsed.
            expression = "case when to_regprocedure('public."+function+"()') is null then "+str(protocols[key])+" else -1 end"
        fields.extend(("'"+key+"'", expression))
    return 'select observation::jsonb || jsonb_build_object('+','.join(fields)+') from ('+QUIESCENCE_SQL+') as q(observation)'


def require_target_protocols(schema, delivery, outbox, deletion):
    values = schema, delivery, outbox, deletion
    if any(type(v) is not int for v in values) or values != (160, 2, 2, 2):
        raise RuntimeError('schema160_target_protocols_required')
