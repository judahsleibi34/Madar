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


def admitted_manifest(root, contract):
    raise RuntimeError('schema160_protected_controller_integration_incomplete')


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
