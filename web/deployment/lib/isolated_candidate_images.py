"""Prepare authenticated image bytes in an enrolled disposable guest only.

This is fixture preparation, not deployment, admission or migration authority.
The existing coordinator and child independently reobserve imported identities.
"""
import hashlib
import json
import os
import subprocess
import tempfile

from .schema148_artifacts import authenticated_archive, provenance_inputs, verify_archive, verify_prepared_candidate_images


def load_member(archive, role, metadata):
    """Hash bounded bytes through the same private FD passed to Docker."""
    if role not in ('backend','frontend') or not 0 < metadata['bytes'] <= 3*1024**3:
        raise RuntimeError('isolated_candidate_member_invalid')
    with tempfile.TemporaryFile(mode='w+b') as frozen:
        value=hashlib.sha256();size=0
        with archive.open(role+'.tar.gz') as source:
            for chunk in iter(lambda:source.read(1024*1024),b''):
                size+=len(chunk)
                if size>metadata['bytes']:raise RuntimeError('isolated_candidate_member_changed')
                value.update(chunk);frozen.write(chunk)
        if size!=metadata['bytes'] or value.hexdigest()!=metadata['sha256']:
            raise RuntimeError('isolated_candidate_member_changed')
        frozen.seek(0)
        result=subprocess.run(['docker','image','load'],stdin=frozen,capture_output=True,timeout=600)
        if result.returncode:raise RuntimeError('isolated_candidate_import_failed')


def prepare(actor, source_guard):
    from .schema160_release import isolated_registration
    from .isolated_release_environment import observe
    from .completed_normal_evidence import measured_record
    from .completed_normal_profile import RECONCILED
    from .control_plane_upgrade import acquire_lock
    if (os.geteuid()!=0 or actor.contract.get('operation')!=RECONCILED.operation
            or actor.document.get('fixture_only') is not True
            or actor.document.get('production_authorization') is not False):
        raise RuntimeError('isolated_candidate_preparation_scope_required')
    upgrade_lock=acquire_lock(actor.ops.upgrade_root/'upgrade.lock',create=False)
    lock=None
    try:
        lock=acquire_lock(actor.ops.state_root/'deploy.lock',create=False)
        source_guard();before=observe();isolated_registration(actor.contract)
        if actor.ops.installed_sha()!=actor.contract['candidate']['controller_sha']:
            raise RuntimeError('isolated_candidate_controller_changed')
        # No import may repair an admitted/consumed operation in place.
        if actor.root.exists() or actor.root.is_symlink():
            raise RuntimeError('isolated_candidate_operation_already_started')
        binding=measured_record(actor.document['application_evidence']['provenance'])
        artifact,run,inputs=provenance_inputs(actor,binding)
        receipt=verify_archive(binding['archive'],artifact,run,
            source_sha=actor.contract['candidate']['source_sha'],
            images=actor.contract['candidate']['images'],expected_inputs=inputs)
        if receipt['build_timestamp']!=actor.document['application_artifacts']['build_timestamp']:
            raise RuntimeError('isolated_candidate_timestamp_changed')
        from .schema148_artifacts import candidate_image_tags
        tags=candidate_image_tags(actor.contract['candidate']['source_sha'])
        # Never overwrite an existing name referring to unrelated image bytes.
        for role,tag in tags.items():
            result=subprocess.run(['docker','image','inspect',tag],capture_output=True,timeout=30)
            if result.returncode==0:
                rows=json.loads(result.stdout)
                if len(rows)!=1 or rows[0]['Id']!=actor.contract['candidate']['images'][role]:
                    raise RuntimeError('isolated_candidate_existing_tag_changed')
            elif b'No such image' not in result.stderr:
                raise RuntimeError('isolated_candidate_image_observation_failed')
        with authenticated_archive(binding['archive'],artifact['digest']) as archive:
            for role in ('backend','frontend'):
                source_guard()
                if observe()!=before:raise RuntimeError('isolated_candidate_environment_changed')
                load_member(archive,role,receipt['archives'][role])
        def command(args):return subprocess.check_output(args,text=True,timeout=30)
        result=verify_prepared_candidate_images(actor.contract,receipt['build_timestamp'],command)
        source_guard()
        if observe()!=before:raise RuntimeError('isolated_candidate_environment_changed')
        return dict(result,preparation_only=True,production_authorization=False)
    finally:
        if lock is not None:os.close(lock)
        os.close(upgrade_lock)
