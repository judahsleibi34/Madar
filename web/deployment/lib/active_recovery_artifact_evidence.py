"""Actual final-image acceptance bindings; no transferred PASS summaries."""
import json
from pathlib import Path
import re
import urllib.request
from deployment.lib.active_recovery_execution import PREPARATION, actual_inline_execution
from deployment.lib.provider_recovery_runtime import protected, readonly_configuration, file_digest

CASES=frozenset({'frontend_api_origin','backend_readiness','local_schema115','existing_authentication',
    'original_mfa_aal2','aal1_privilege_denied','session_cookie_policy','tenant_isolation',
    'business_permissions','forms','reservations','builder','schema115_ecommerce',
    'restricted_write_denial','private_normal_write_activation','singleton_workers',
    'required_integrations','rollback_current_data'})
NODE1_CONFIGURATION=Path('/etc/madar/node1-backup.env')

def verify_artifact_acceptance(plan):
    index=PREPARATION/'artifact-acceptance'/('index-'+plan.acceptance_execution_sha256+'.json')
    location=json.loads(protected(index,private=True).read_text())
    path=Path(location['execution'])
    if (path.parent.parent!=PREPARATION/'artifact-acceptance' or path.name!='execution.json'
            or not re.fullmatch(r'run-[0-9a-f]{12}',path.parent.name)):
        raise RuntimeError('artifact_execution_path_invalid')
    report,record=actual_inline_execution(path,plan.acceptance_execution_sha256,
        'actual-final-application-artifact-acceptance','web/scripts/verify_final_application_artifacts.py',source_directory='source')
    observations=report.get('cases',{})
    if (report.get('operation')!='actual-final-application-artifact-acceptance'
            or report.get('source_sha')!=plan.source_sha or report.get('images')!=plan.candidate_images
            or report.get('checkpoint_manifest_sha256')!=plan.checkpoint_manifest_sha256
            or report.get('local_configuration_sha256')!=plan.retained_inputs['local_configuration']
            or report.get('schema')!=115 or report.get('production_modified') is not False
            or report.get('migrations_executed') is not False or report.get('private_fixture_only') is not True
            or set(observations)!=CASES or any(not isinstance(row,dict) or row.get('verified') is not True
                or not row.get('observations') for row in observations.values())):
        raise RuntimeError('artifact_acceptance_incomplete_or_incompatible')
    # The executable verifier must be the final Git revision's tracked verifier,
    # whose bytes are bound in the eventual approved source package as well.
    import subprocess
    import hashlib
    for relative,expected in record['source_files'].items():
        result=subprocess.run(['/usr/bin/git','-c','safe.directory=/opt/madar-development/repository','-c','core.hooksPath=/dev/null','-c','core.fsmonitor=false','show',plan.source_sha+':'+relative],
            cwd='/opt/madar-development/repository',capture_output=True,timeout=10)
        if result.returncode or hashlib.sha256(result.stdout).hexdigest()!=expected:
            raise RuntimeError('artifact_verifier_source_revision_changed')
    replica=report.get('node1_replica',{})
    if (set(replica)!={'host','filesystem_uuid','configuration_sha256'} or replica['host']!='madar-node1-lan'
            or not re.fullmatch('[0-9a-f-]{36}',replica['filesystem_uuid'])
            or file_digest(readonly_configuration(NODE1_CONFIGURATION,private=True))!=replica['configuration_sha256']):
        raise RuntimeError('artifact_replica_configuration_changed')
    return report

def public_normal_observations(plan,slot):
    observations={}
    for name,url in {'frontend':'https://madarportal.com/','api':'https://api.madarportal.com/',
            'version':'https://api.madarportal.com/health/version',
            'recovery':'https://api.madarportal.com/health/recovery',
            'readiness':'https://api.madarportal.com/health/ready'}.items():
        request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
        with urllib.request.urlopen(request,timeout=10) as response:
            if response.status!=200:raise RuntimeError('normal_public_endpoint_unavailable')
            body=response.read(65536);observations[name]={'http_status':response.status}
        if name in {'version','recovery','readiness'}:observations[name]['body']=json.loads(body)
    version=observations['version']['body']
    if version.get('release_sha')!=plan.source_sha or version.get('release_slot')!=slot or (version.get('schema_compatible_min'),version.get('schema_compatible_max'))!=(115,115):
        raise RuntimeError('normal_public_release_changed')
    if observations['recovery']['body']!={'restricted':False,'business_writes_enabled':True}:
        raise RuntimeError('normal_public_write_restrictions_changed')
    if observations['readiness']['body'].get('ready') is not True:raise RuntimeError('normal_public_not_ready')
    return observations
