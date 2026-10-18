"""Evidence accounting only; never credentials, authority or a deployment actor."""
import re

STATES={'PASS','FAIL','PARTIAL','BLOCKED','NOT TESTED'}
GATES=('identity','ancestry','ci','source_integrity','release_metadata','artifacts',
       'controller','worker_inventory','delivery_protocol','outbox_protocol','deletion_worker',
       'provider_lifecycle','database_migration','intermediate_read_only','forward_repair',
       'authentication','mfa','storage','tenant_isolation','reservations','notifications',
       'deletion_ownership','backup','restore','pitr','replica','staging',
       'controller_installation','main_protection','independent_review','production_authorization')


def evaluate(source_sha,evidence=None):
    if not re.fullmatch('[0-9a-f]{40}',str(source_sha)):raise ValueError('Exact source required')
    evidence=evidence or {'version':1,'source_sha':source_sha,'gates':{}}
    if (set(evidence)!={'version','source_sha','gates'} or type(evidence['version']) is not int
            or evidence['version']!=1 or evidence['source_sha']!=source_sha
            or not isinstance(evidence['gates'],dict) or set(evidence['gates'])-set(GATES)):
        raise ValueError('Unknown or different-source readiness evidence')
    observed={}
    for key in GATES:
        row=evidence['gates'].get(key)
        if row is None:
            observed[key]={'status':'NOT TESTED'};continue
        if (not isinstance(row,dict) or set(row)!={'status','evidence_sha256'} or row['status'] not in STATES
                or not re.fullmatch('[0-9a-f]{64}',str(row['evidence_sha256']))):
            raise ValueError('Invalid bounded evidence reference')
        observed[key]=dict(row)
    # These source-known blockers cannot be turned into authority by supplying
    # a local PASS packet. Future reviewed code must establish real acceptance.
    for key,status in {'controller':'BLOCKED','controller_installation':'BLOCKED',
                       'deletion_worker':'BLOCKED','deletion_ownership':'FAIL',
                       'production_authorization':'BLOCKED'}.items():
        observed[key]={'status':status,'reason':'Known source limitation; local evidence cannot authorize'}
    return {'version':1,'source_sha':source_sha,'schema_origin':146,'schema_target':149,
            'gates':observed,'assessment':'NOT READY','production_authorized':False,
            'actions_performed':False,'limitations':['Evidence accounting, not protected controller acceptance',
                'Synthetic evidence is not current-production acceptance or independent approval']}
