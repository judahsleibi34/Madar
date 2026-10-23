#!/usr/bin/env python3
"""Run discovered routine SQL on the owned minimal CI PostgreSQL fixture only.

The retained full150 business rehearsal remains separate. Coordinated/unknown
SQL is reported BLOCKED rather than executed on inadequate fixtures. No result
here establishes full application staging or protected production admission.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from deployment.lib.migration_inventory import discover,canonical
from deployment.lib.migration_plan import generate
from deployment.lib.migration_rehearsal import connect,run


def main():
    root=Path(__file__).resolve().parents[2]
    source=os.environ['CI_SOURCE_SHA']; baseline=os.environ['CI_HISTORY_BASE_SHA']
    before=discover(root,source_sha=baseline,history_base_sha=baseline)
    inventory=discover(root,source_sha=source,history_base_sha=baseline)
    desired=generate(root,inventory,origin=before.target)
    value=desired.document()
    report={'version':1,'source_sha':source,'plan_sha256':desired.sha256,
            'coverage':'minimal-catalog-native-database','production_authorized':False,
            'full_application_acceptance':False,'desired_origin':before.target,
            'target_schema':value['target_schema'],'risk_class':value['risk_class']}
    if not value['migrations']:
        report.update(status='NOT_APPLICABLE',reason='application_only_no_database_work')
    elif (value['risk_class']!='A' or not value['compatibility_covers_path']
            or value['execution_class']!='transactional' or value['protected_control_plane_changed']):
        # Preserve classification/identity of the actual source-to-source plan.
        # A newer fixture must never replace it with an empty or safer tail.
        report.update(status='BLOCKED',reason='stronger_rehearsal_or_compatibility_required')
    else:
        dsn=os.environ['GENERIC_MIGRATION_SYNTHETIC_DATABASE_DSN']
        with connect(dsn) as db:
            origin=db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0]
            cluster=db.execute('select system_identifier::text from pg_control_system()').fetchone()[0]
        if origin!=value['origin_schema']:
            report.update(status='BLOCKED',reason='synthetic_fixture_origin_mismatch',observed_origin=origin)
        else:
            backup=Path(os.environ['GENERIC_MIGRATION_SYNTHETIC_BACKUP'])
            def verify_backup(directory):
                metadata=json.loads((directory/'manifest.json').read_bytes())
                body=(directory/'database.dump').read_bytes()
                if (hashlib.sha256(body).hexdigest()!=metadata['sha256'] or body[:5]!=b'PGDMP'
                        or metadata['system_identifier']!=cluster): raise RuntimeError('candidate_rehearsal_backup_mismatch')
            with tempfile.TemporaryDirectory(prefix='madar-native-candidate-') as temporary:
                result=run(root,inventory,desired,dsn=dsn,state_file=Path(temporary)/'attempt.json',
                           backup_dir=backup,backup_verifier=verify_backup)
            report.update(status='PASS',observed_origin=origin,observed_target=result['observed_schema'],
                          executed_plan_sha256=desired.sha256,migrations=value['migrations'])
    sys.stdout.buffer.write(canonical(report))
    return 0


if __name__=='__main__': raise SystemExit(main())
