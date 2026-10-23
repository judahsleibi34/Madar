#!/usr/bin/env python3
"""INSPECT or REHEARSE exact fresh images on the owned already-committed149 stack.

No migrations, production issuer or automatic recovery. Interrupted scopes are
retained and require explicit investigation; older acceptance is archived.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import time

import manage
import smoke
import independent_recovery as recovery
import schema149_acceptance as acceptance
from fresh_artifact_acceptance import authenticated_archive, import_authenticated_image

SERVICES=('postgres','redis','auth','rest','storage','gateway','backend',
          'notification-worker','accepted-frontend','frontend')


def inspect(mode, directory, source):
    if mode not in {'INSPECT','REHEARSE'} or not re.fullmatch('[0-9a-f]{40}',source):
        raise RuntimeError('Explicit image acceptance mode/source required')
    manage.require_staging_host()
    runtime=Path.home()/acceptance.PROJECT
    with acceptance.target(runtime):
        state=manage.state();manage.attest_resources();manage.require_database_marker()
        if manage.sql("select schema_version||':'||notification_delivery_protocol()||':'||notification_outbox_protocol() from application_schema_state where contract_key='core';")!='149:2:2':
            raise RuntimeError('Image acceptance requires committed149 and both protocols2')
        artifact,run,images,receipt=acceptance.artifacts(directory,source)
        if mode=='INSPECT':
            return {'mode':mode,'source_sha':source,'current_source':state['source_sha'],
                    'schema':149,'images':images,'mutations_executed':False}
        scope=runtime/('fresh149-images-'+source)
        if scope.exists() or scope.is_symlink():raise RuntimeError('Image acceptance attempt already consumed')
        if shutil.disk_usage(runtime).free<8*1024**3:raise RuntimeError('Fresh image disk headroom insufficient')
        scope.mkdir(mode=0o700)
        acceptance.regular(runtime/'schema149-acceptance.json')
        recovery_value=(runtime/'schema149-acceptance.json').read_bytes()
        (scope/'previous-acceptance.json').write_bytes(recovery_value);(scope/'previous-acceptance.json').chmod(0o600)
        with authenticated_archive(directory/'candidate.zip',artifact['digest']) as archive:
            for role in ('backend','frontend'):
                import_authenticated_image(archive,role,receipt['archives'][role],scope/(role+'.tar.gz'))
                value=json.loads(manage.docker('image','inspect',images[role]))[0]
                labels=value['Config'].get('Labels',{})
                if (value['Id']!=images[role] or labels.get('com.madar.release.sha')!=source
                        or labels.get('org.opencontainers.image.revision')!=source
                        or labels.get('com.madar.build.mode')!='fresh-locked-ci'):
                    raise RuntimeError('Fresh imported image identity mismatch')
        overlay=runtime/('image-selection-'+source+'.json')
        manage.private_write(overlay.name,json.dumps({'services':{name:{'image':images['frontend' if name=='accepted-frontend' else 'backend']}
            for name in ('backend','notification-worker','deletion-worker','accepted-frontend')}}))
        args=('--file',str(runtime/'acceptance-compose.json'),'--file',str(overlay))
        started=time.monotonic()
        manage.compose('--file',str(runtime/'acceptance-compose.json'),'stop','--timeout','20',
                       'frontend','accepted-frontend','backend','notification-worker','deletion-worker')
        manage.select_source(source)
        env=(runtime/'application.env').read_text()
        env=re.sub(r'^MADAR_BUILD_TIMESTAMP=.*$', 'MADAR_BUILD_TIMESTAMP='+receipt['build_timestamp'],env,flags=re.M)
        manage.private_write('application.env',env)
        manage.compose(*args,'up','--detach','--wait','--wait-timeout','150',*SERVICES)
        manage.compose(*args,'create','deletion-worker')
        manage.attest_resources();manage.require_database_marker()
        #149 has no complete deletion ownership RPC: prove the new image refuses
        #consumption. The existing request queue must remain untouched.
        before=manage.sql('select count(*) from data_deletion_requests;')
        identifier=manage.compose(*args,'ps','--all','-q','deletion-worker').decode().strip()
        if not identifier:raise RuntimeError('Held deletion container identity missing')
        result=subprocess.run(manage.DOCKER+['start','--attach',identifier],capture_output=True,timeout=30)
        row=json.loads(manage.docker('inspect',identifier))[0]
        if (result.returncode==0 or row['State']['Running'] or row['State']['ExitCode']==0
                or row['HostConfig']['RestartPolicy']['Name']!='no'
                or b'deletion.ownership_protocol_required' not in result.stdout+result.stderr
                or manage.sql('select count(*) from data_deletion_requests;')!=before):
            raise RuntimeError('Unsafe deletion worker was not held before consumption')
        smoke.main()
        old=json.loads(acceptance.regular(Path.home()/'madar-hardening-20261016/smoke-fixture.json'))
        identity=recovery.original_identity_acceptance(old)
        cancellation=acceptance.cancellation_probe()
        code={}
        for service in ('backend','notification-worker','accepted-frontend'):
            identifier=manage.compose(*args,'ps','-q',service).decode().strip()
            row=json.loads(manage.docker('inspect',identifier))[0]
            if row['Image']!=images['frontend' if service=='accepted-frontend' else 'backend']:
                raise RuntimeError('Actual runtime image changed')
            if any(m.get('Destination','').startswith('/app') for m in row.get('Mounts',[])):
                raise RuntimeError('Runtime source overlay is not fresh artifact acceptance')
            if service=='backend':
                for name in ('routes/calendar_routes.py','workers/data_deletion_worker.py','workers/notification_worker.py'):
                    actual=manage.docker('exec',identifier,'python','-c',
                        "import hashlib;print(hashlib.sha256(open('/app/"+name+"','rb').read()).hexdigest())").decode().strip()
                    expected=hashlib.sha256((manage.REPOSITORY/'web/backend'/name).read_bytes()).hexdigest()
                    if actual!=expected:raise RuntimeError('Runtime source bytes changed')
                    code[name]=actual
        report={'scope':'fresh exact images on owned independent149 restored runtime','source_sha':source,
            'previous_source_sha':state['source_sha'],'images':images,'run_id':run['id'],'artifact_id':artifact['id'],
            'schema':149,'delivery_protocol':2,'outbox_protocol':2,'migration_replayed':False,'source_overlay_used':False,
            'native_auth_mfa_storage_outbox_delivery_frontend_readiness':True,'original_identity_acceptance':identity,
            'deletion_cancellation':cancellation,'deletion_worker_refused_unsafe_protocol':True,
            'deletion_worker_retained_stopped':True,'runtime_code_sha256':code,
            'elapsed_seconds':round(time.monotonic()-started,3),'production_modified':False,
            'production_authorized':False,'limitations':['full deletion lifecycle blocked','not146 privileged controller acceptance',
                'same VM, not off-host recovery or full application PITR','not complete product E2E']}
        manage.private_write('schema149-acceptance.json',json.dumps(report,indent=2)+'\n')
        return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('INSPECT','REHEARSE'),nargs='?',default='INSPECT')
    parser.add_argument('--artifacts',type=Path,required=True);parser.add_argument('--source-sha',required=True)
    args=parser.parse_args();print(json.dumps(inspect(args.mode,args.artifacts,args.source_sha),sort_keys=True))
