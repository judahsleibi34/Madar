"""Root-selected targets; publication and test fixtures cannot authorize SQL.

Canonical history is always authenticated first. A separately pinned fixture
history is usable only in an independently observed isolated execution realm;
it never replaces canonical SQL or the production inventory.
"""
from pathlib import Path
import hashlib,re
from .migration_inventory import Inventory,MigrationBytes,GitSource,discover,digest,strict_json
from .migration_drift import history_digest
from .provider_recovery_runtime import protected

ROOT=Path('/etc/madar/automatic-selections')
FIXTURE_PREFIX='web/staging/fixtures/automatic-migrations/'
FIELDS={'version','environment_id','database_system_identifier','source_sha','controller_sha',
        'origin_schema','target_schema','history','plan_sha256','images_sha256','routine_policy_sha256'}


def fixture_inventory(git,canonical,history):
    fields={'kind','manifest_path','manifest_sha256','canonical_schema','canonical_history_sha256'}
    if (set(history)!=fields or history['kind']!='isolated-fixture'
            or not isinstance(history['manifest_path'],str)
            or not re.fullmatch(re.escape(FIXTURE_PREFIX)+r'[a-z0-9_-]+/history.json',history['manifest_path'])
            or history['canonical_schema']!=160
            or history_digest(canonical,160)!=history['canonical_history_sha256']):
        raise RuntimeError('automatic_fixture_history_not_enrolled')
    files=git.files(canonical.source_sha,FIXTURE_PREFIX)
    body=files.get(history['manifest_path'],b'')
    if hashlib.sha256(body).hexdigest()!=history['manifest_sha256']:
        raise RuntimeError('automatic_fixture_manifest_substituted')
    manifest=strict_json(body)
    if (set(manifest)!={'version','kind','initial_schema','migrations'} or manifest['version']!=1
            or manifest['kind']!='isolated-test-only-history' or manifest['initial_schema']!=900160
            or not isinstance(manifest['migrations'],list) or not 2<=len(manifest['migrations'])<=10):
        raise RuntimeError('automatic_fixture_manifest_invalid')
    migrations=[]
    for number,row in enumerate(manifest['migrations'],manifest['initial_schema']):
        if (set(row)!={'number','path','sha256'} or row['number']!=number
                or not re.fullmatch(re.escape(FIXTURE_PREFIX)+r'[a-z0-9_-]+/[a-z0-9_]+\.sql',str(row['path']))
                or row['path'] not in files or hashlib.sha256(files[row['path']]).hexdigest()!=row['sha256']):
            raise RuntimeError('automatic_fixture_sql_substituted')
        migrations.append(MigrationBytes(number,row['path'],row['path'],files[row['path']]))
    # The first entry truthfully records the separately governed initialization,
    # including its protocol fixture. It is never an automatic forward step.
    return Inventory(canonical.source_sha,canonical.history_base_sha,tuple(migrations),(),
        tuple(sorted((str(k),str(v)) for k,v in history.items())))


def select(operations,source,proof,policy,routine,origin):
    canonical=discover(operations.repo,source_sha=source,history_base_sha=proof['history_base_sha'])
    path=ROOT/(source+'.json')
    if not path.exists() and not path.is_symlink():
        # No selection means NO SQL, even when newer SQL has been published.
        return canonical,origin,None
    value=strict_json(protected(path,private=True).read_bytes())
    if (not isinstance(value,dict) or set(value)!=FIELDS or type(value['version']) is not int or value['version']!=1
            or any(value[k]!=expected for k,expected in (
                ('environment_id',policy['environment_id']),('source_sha',source),
                ('controller_sha',policy['controller_sha']),('database_system_identifier',routine['database_system_identifier']),
                ('origin_schema',origin),('images_sha256',digest(proof['images'])),('routine_policy_sha256',digest(routine))))
            or type(value['origin_schema']) is not int or type(value['target_schema']) is not int
            or not origin<=value['target_schema']<10**9 or not isinstance(value['history'],dict)
            or not re.fullmatch('[a-f0-9]{64}',str(value['plan_sha256']))):
        raise RuntimeError('automatic_release_selection_substituted')
    history=value['history']
    if history=={'kind':'canonical'}:inventory=canonical
    elif history.get('kind')=='isolated-fixture' and policy['environment']=='isolated-test':
        inventory=fixture_inventory(GitSource(operations.repo),canonical,history)
    else:raise RuntimeError('automatic_release_history_scope_refused')
    inventory.forward(origin,value['target_schema'])
    return inventory,value['target_schema'],value
