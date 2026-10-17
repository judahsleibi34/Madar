#!/usr/bin/env python3
"""INSPECT/VALIDATE only. No execution, preparation, reconciliation or approval mutation."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import socket
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from deployment.lib.schema148_release import source_manifest,QUIESCENCE_SQL,consumer_inventory,require_database_quiescence
from deployment.lib.schema148_readiness import evaluate

ROOT=Path(__file__).resolve().parents[2]
RECONCILIATION_SQL="""select json_build_object(
 'counts',(select json_object_agg(status,amount) from (select status,count(*) amount from public.notification_deliveries group by status) s),
 'processing_sample',(select coalesce(json_agg(d),'[]'::json) from (
   select encode(sha256(convert_to(id::text,'UTF8')),'hex') delivery_reference_sha256,channel,attempts,
     case when processing_lease_until>clock_timestamp() then 'valid' else 'expired_or_missing' end lease,
     'uncertain_requires_independent_provider_evidence'::text provider_outcome
   from public.notification_deliveries where status='processing' order by id limit 500) d))"""


def command(args):
    result=subprocess.run(args,capture_output=True,text=True,timeout=15)
    if result.returncode:raise RuntimeError('Read-only inspection failed; raw output suppressed')
    return result.stdout.strip()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('INSPECT','VALIDATE_SOURCE','RECONCILE_REPORT'),nargs='?',default='VALIDATE_SOURCE')
    parser.add_argument('--expected-host');parser.add_argument('--expected-system-identifier')
    parser.add_argument('--database-container');parser.add_argument('--database',default='postgres')
    parser.add_argument('--docker-sudo',action='store_true')
    parser.add_argument('--environment',choices=('production','staging'),default='production')
    args=parser.parse_args()
    source=command(['git','-C',str(ROOT),'rev-parse','HEAD'])
    origin=command(['git','-C',str(ROOT),'remote','get-url','origin'])
    if origin not in {'git@github.com:judahsleibi34/Madar.git','https://github.com/judahsleibi34/Madar.git'}:
        raise RuntimeError('Unexpected repository origin')
    dirty=command(['git','-C',str(ROOT),'status','--porcelain'])
    manifest=source_manifest(ROOT);facts={'manifest':manifest,'repository_clean':not bool(dirty)}
    evidence={}
    def observed(gate,value,passed=True):
        evidence[gate]={'status':'PASS' if passed else 'FAIL','source_sha':source,'scope':args.environment,
            'observed_at':datetime.now(timezone.utc).isoformat(),
            'sha256':hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()}
    observed('source.exact',{'origin':origin,'sha':source},not dirty)
    observed('source.release_manifest',manifest)
    # Two selected migrations are verified, not a claim of full historical SQL review.
    facts['selected_migrations_verified']=[147,148]
    if args.mode!='VALIDATE_SOURCE':
        if (not args.expected_host or socket.gethostname()!=args.expected_host
                or not re.fullmatch('[0-9]+',args.expected_system_identifier or '')
                or not re.fullmatch('[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}',args.database_container or '')
                or not re.fullmatch('[a-zA-Z_][a-zA-Z0-9_]*',args.database)):
            raise RuntimeError('Explicit host, cluster and database identity required')
        docker=['sudo','-n','docker'] if args.docker_sudo else ['docker']
        def query(body):
            text=command(docker+['exec',args.database_container,'psql','-XqAt','-v','ON_ERROR_STOP=1','-U','postgres','-d',args.database,'-c',
                "BEGIN READ ONLY; SET LOCAL statement_timeout='5s'; "+body+'; COMMIT;'])
            return json.loads(text)
        native=query(QUIESCENCE_SQL)
        if native['system_identifier']!=args.expected_system_identifier:raise RuntimeError('Different PostgreSQL cluster')
        facts['database']=native
        observed('infrastructure.host',args.expected_host)
        observed('infrastructure.database',native)
        observed('database.origin',native,native['schema']==146)
        try:
            require_database_quiescence(native,{'database':{'system_identifier':args.expected_system_identifier}},146)
            observed('database.quiescence',native)
        except RuntimeError:evidence['database.quiescence']={'status':'BLOCKED'}
        facts['notification_reconciliation']=query(RECONCILIATION_SQL)
        facts['reconciliation_limit']=500
        facts['provider_outcomes_inferred']=False
        facts['production_changed']=False
        evidence['infrastructure.worker_inventory']={'status':'PARTIAL'}
        # Process/container status alone cannot prove exclusive consumer ownership.
        facts['worker_inventory_requires_protected_policy']=True
    result=evaluate(evidence,source_sha=source,environment=args.environment)
    result.update({'mode':args.mode,'facts':facts,'mutations_performed':False})
    print(json.dumps(result,indent=2,sort_keys=True))


if __name__=='__main__':
    try:main()
    except (RuntimeError,ValueError,OSError,subprocess.TimeoutExpired) as error:
        raise SystemExit(str(error)) from None
