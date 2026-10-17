"""Evidence accounting only: this model can never issue production authority."""
from datetime import datetime,timezone
import re

STATES=frozenset({'PASS','FAIL','PARTIAL','BLOCKED','NOT TESTED'})
GROUPS={
 'source':('exact','dependencies','ci_backend','ci_frontend','immutable_migrations','release_manifest'),
 'infrastructure':('host','capacity','database','worker_inventory','redis','backup_paths','network'),
 'database':('origin','structure','migration_history','quiescence','preservation','locks'),
 'security':('controller','privileges','secrets_identity','write_authority'),
 'recovery':('backup','independent_application','replica','checkpoints','forward_plan'),
 'application':('backend','frontend','workers','auth','mfa','storage','tenant_isolation','reservations','notifications','readiness'),
 'operator':('maintenance','artifacts','reconciliation','rollback_limits','authorization'),
}
GATES=tuple(group+'.'+name for group,names in GROUPS.items() for name in names)


def evaluate(evidence,*,source_sha,environment,now=None):
    if not re.fullmatch('[0-9a-f]{40}',source_sha) or environment not in {'production','staging'}:
        raise ValueError('schema148_readiness_identity_invalid')
    if not isinstance(evidence,dict) or set(evidence)-set(GATES):
        raise ValueError('schema148_readiness_unknown_gate')
    now=now or datetime.now(timezone.utc)
    result={}
    for gate in GATES:
        row=evidence.get(gate,{'status':'NOT TESTED'})
        status=row.get('status') if isinstance(row,dict) else None
        reason='Evidence not supplied'
        if status not in STATES:
            status='FAIL';reason='Invalid evidence status'
        elif status=='PASS':
            if (not re.fullmatch('[0-9a-f]{64}',str(row.get('sha256','')))
                    or row.get('source_sha')!=source_sha):
                status='FAIL';reason='Missing or different exact-source evidence'
            elif gate.startswith('operator.'):
                status='BLOCKED';reason='Requires independent protected authorization; a report grants no authority'
            elif gate.startswith('source.'):
                reason='Source evidence recorded; independent admission still required'
            elif row.get('scope')!=environment:
                status='PARTIAL';reason='Evidence belongs to a different environment'
            else:
                try:
                    instant=datetime.fromisoformat(row['observed_at'])
                    age=(now-instant).total_seconds()
                    if instant.tzinfo is None or not 0<=age<=300:raise ValueError()
                    reason='Current evidence recorded; independent admission still required'
                except (KeyError,TypeError,ValueError):
                    status='BLOCKED';reason='Operational evidence missing, stale or from the future'
        else:
            reason={'FAIL':'Gate failed','PARTIAL':'Evidence incomplete','BLOCKED':'External prerequisite missing','NOT TESTED':'Check not executed'}[status]
        result[gate]={'status':status,'reason':reason}
        if isinstance(row,dict) and re.fullmatch('[0-9a-f]{64}',str(row.get('sha256',''))):result[gate]['sha256']=row['sha256']
    technical=all(row['status']=='PASS' for gate,row in result.items() if not gate.startswith('operator.'))
    return {'source_sha':source_sha,'environment':environment,'production_authorized':False,
        'assessment':'TECHNICALLY READY FOR OPERATOR REVIEW' if technical else 'NOT READY',
        'gates':result}
