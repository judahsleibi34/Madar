#!/usr/bin/env python3
"""INSPECT/REHEARSE a fenced synthetic149 backup and independent component restore.

Only the new Phase V project is eligible. No production paths, SQL cutover,
application PITR, live restore or backup deletion is implemented.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import time
from uuid import uuid4

import manage
import restore
import independent_recovery as recovery
import schema149_acceptance as acceptance
import schema149_provider_rehearsal as providers
from deployment.lib.schema149_provider_lifecycle import ProviderMaintenance, digest


def run(mode):
    if mode not in {'INSPECT','REHEARSE'}:raise RuntimeError('backup149_mode_invalid')
    manage.require_staging_host()
    runtime=Path.home()/acceptance.PROJECT
    with acceptance.target(runtime):
        manage.state();manage.attest_resources();manage.require_database_marker()
        if providers.sql("select schema_version||':'||notification_delivery_protocol()||':'||notification_outbox_protocol() from application_schema_state where contract_key='core';")!='149:2:2':
            raise RuntimeError('backup149_origin_incompatible')
        root=runtime/'backup149-journal'
        if mode=='INSPECT':return {'mode':mode,'schema':149,'existing_attempt':root.exists(),'mutations_executed':False}
        if root.exists() or root.is_symlink():raise RuntimeError('backup149_attempt_already_consumed')
        root.mkdir(mode=0o700)
        files=runtime/'backup149-files'
        if files.exists() or files.is_symlink():raise RuntimeError('backup149_archive_scope_already_consumed')
        files.mkdir(mode=0o700)
        journal=providers.Journal(root);actor=providers.StagingActor(runtime,journal)
        driver=ProviderMaintenance(actor.binding,journal,actor)
        marker=runtime/'backup149-interlock.json'
        verify=actor.verify_effect
        def arm(binding,preimage):
            if marker.exists() or marker.is_symlink():raise RuntimeError('backup149_interlock_exists')
            manage.private_write(marker.name,json.dumps({'binding':binding,'preimage_sha256':digest(preimage)})+'\n')
        actor.arm_boot_interlock=arm
        actor.verify_effect=lambda step,binding,preimage: (
            providers.private(marker)=={'binding':binding,'preimage_sha256':digest(preimage)}
            if step=='arm_boot_interlock' else verify(step,binding,preimage))
        db=manage.database_container()
        # Capture ORIGINAL full role DDL before any NOLOGIN alteration. Backup
        # data is later taken with all writers fenced, never from a moving API.
        roles=manage.docker('exec',db,'pg_dumpall','-U','postgres','--roles-only')
        role_root=providers.sql(recovery.ROLE_FINGERPRINT)
        restore.write_binary(files/'roles.sql',roles)
        with (files/'roles.sql').open('rb') as durable:os.fsync(durable.fileno())
        descriptor=os.open(files,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(descriptor)
        finally:os.close(descriptor)
        started=time.monotonic();driver.prepare()
        if driver._preimage()['roles']['all_roles_sha256']!=role_root:raise RuntimeError('backup149_role_preimage_changed')
        # Production fence() requires origin146. This separate component backup
        # starts on149 and proves149 quiescence after the same ordered effects.
        for step in providers.FENCE_STEPS:driver._effect(step)
        driver.require_quiescence(149)
        before=json.loads(providers.sql(restore.FINGERPRINT_SQL))
        objects=restore.inventory(acceptance.PROJECT+'_objects')
        dump=manage.docker('exec',db,'pg_dump','-U','postgres','--format=custom','madar_hardening')
        archive=restore.helper(acceptance.PROJECT+'_objects',
            "import sys,tarfile;t=tarfile.open(fileobj=sys.stdout.buffer,mode='w|');t.add('/objects',arcname='.')")
        acceptance.archive_members(archive)
        if before!=json.loads(providers.sql(restore.FINGERPRINT_SQL)) or objects!=restore.inventory(acceptance.PROJECT+'_objects'):
            raise RuntimeError('backup149_source_changed_while_fenced')
        for name,value in (('database.dump',dump),('objects.tar',archive)):
            restore.write_binary(files/name,value)
        snapshot='backup149-fenced-snapshot.json'
        manage.private_write(snapshot,json.dumps({'rows_sha256':digest(before)})+'\n')
        identifier=None;target='madar-149-restore-'+uuid4().hex[:12]
        volume=target+'-objects';owner='schema149-phase5-component-restore'
        def sql(statement):
            return manage.docker('exec','-i',identifier,'psql','-XqAt','-U','postgres','-d','madar_hardening',
                '-v','ON_ERROR_STOP=1',data=statement.encode()).decode().strip()
        try:
            identifier=manage.docker('create','--name',target,'--network=none','--memory=512m','--cpus=0.5',
                '--pids-limit=128','--label','com.madar.staging.owner='+owner,
                '--tmpfs','/var/lib/postgresql/data:rw,noexec,nosuid,size=768m',
                '--env','POSTGRES_HOST_AUTH_METHOD=trust',actor.rows['postgres']['Image']).decode().strip()
            if not re.fullmatch('[0-9a-f]{64}',identifier):raise RuntimeError('backup149_target_identity_missing')
            manage.docker('start',identifier)
            for _ in range(60):
                result=__import__('subprocess').run(manage.DOCKER+['exec',identifier,'pg_isready','-U','postgres'],capture_output=True,timeout=3)
                if result.returncode==0:break
                time.sleep(1)
            else:raise RuntimeError('backup149_target_not_ready')
            ddl='\n'.join(line for line in roles.decode().splitlines() if line.strip()!='CREATE ROLE postgres;')+'\n'
            manage.docker('exec','-i',identifier,'psql','-Xq','-U','postgres','-v','ON_ERROR_STOP=1',data=ddl.encode())
            manage.docker('exec',identifier,'createdb','-U','postgres','madar_hardening')
            manage.docker('exec','-i',identifier,'pg_restore','-U','postgres','--exit-on-error','--single-transaction',
                '-d','madar_hardening',data=dump)
            if json.loads(sql(restore.FINGERPRINT_SQL))!=before:raise RuntimeError('backup149_restored_rows_sequences_changed')
            if sql(recovery.ROLE_FINGERPRINT)!=role_root:raise RuntimeError('backup149_original_role_state_not_restored')
            if sql("select schema_version||':'||notification_delivery_protocol()||':'||notification_outbox_protocol() from application_schema_state where contract_key='core';")!='149:2:2':
                raise RuntimeError('backup149_restored_protocols_incompatible')
            if sql("select has_table_privilege('service_role','notification_outbox','UPDATE') or has_table_privilege('service_role','notification_deliveries','UPDATE');")!='f':
                raise RuntimeError('backup149_legacy_queue_grants_restored')
            manage.docker('volume','create','--label','com.madar.staging.owner='+owner,volume)
            restore.helper(volume,"import sys,tarfile;t=tarfile.open(fileobj=sys.stdin.buffer,mode='r|');t.extractall('/objects',filter='data')",data=archive,writable=True)
            if restore.inventory(volume)!=objects:raise RuntimeError('backup149_restored_object_bytes_changed')
            result={'scope':'fenced149 backup and independent component restore; not full application recovery',
                'source_sha':actor.binding['source_sha'],'schema':149,'protocols':[2,2],
                'original_roles_captured_before_fence':True,'fenced_role_state_not_mistaken_for_original':True,
                'database_rows_sequences_preserved':True,'auth_mfa_storage_tables_preserved':True,
                'object_bytes_preserved':True,'legacy_queue_grants_remain_denied':True,
                'independent_postgresql_cluster':True,'network':'none','production_modified':False,
                'full_application_restore':False,'off_host':False,'pitr':False,
                'archive_sha256':{name:hashlib.sha256(value).hexdigest() for name,value in
                    (('database.dump',dump),('roles.sql',roles),('objects.tar',archive))},
                'elapsed_seconds':round(time.monotonic()-started,3)}
            manage.private_write('backup149-result.json',json.dumps(result,indent=2)+'\n')
        finally:
            if identifier:
                row=json.loads(manage.docker('inspect',identifier))[0]
                if row['Config'].get('Labels',{}).get('com.madar.staging.owner')!=owner:
                    raise RuntimeError('backup149_cleanup_ownership_changed')
                manage.docker('rm','--force',identifier)
        providers.recover(runtime,driver,actor,snapshot_name=snapshot,report_name='backup149-provider-recovery.json')
        return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('INSPECT','REHEARSE'),nargs='?',default='INSPECT')
    print(json.dumps(run(parser.parse_args().mode),sort_keys=True))
