"""Read-only, private operator observation of a schema150 maintenance journal.

No runtime transport, source registration, approval, grant or recovery effects.
The last quiescence is historical evidence, never current database acceptance.
"""
from __future__ import annotations
import json
from pathlib import Path
import re

from deployment.lib.completed_normal_admission import ADMISSIONS, digest, validate_provider_preparation150
from deployment.lib.provider_recovery_runtime import protected
from deployment.lib.schema150_provider_lifecycle import ProviderMaintenance150, ProtectedProviderJournal, digest as journal_digest
from deployment.lib.schema150_actor_inventory import validate_inventory


def _document(path):
    source=protected(path,private=True)
    if source.stat().st_size>4*1024*1024:raise RuntimeError('schema150_status_input_limit')
    return json.loads(source.read_bytes())


def inspect_maintenance(context):
    if not isinstance(context,str) or not re.fullmatch('[0-9a-f]{64}',context):
        raise RuntimeError('schema150_status_exact_context_required')
    root=ADMISSIONS/context
    admission=_document(root/'admission.json')
    contract=admission.get('contract')
    validate_provider_preparation150(contract)
    if digest(contract)!=context or admission.get('operation')!=contract['operation']:
        raise RuntimeError('schema150_status_admission_changed')
    journal=ProtectedProviderJournal(root/'provider-journal')
    rows=journal.read()
    if not rows:raise RuntimeError('schema150_status_prepared_journal_required')
    binding=rows[0]['payload'].get('binding')
    if (not isinstance(binding,dict) or binding.get('context_sha256')!=context
            or binding.get('source_sha')!=contract['candidate']['source_sha']
            or binding.get('controller_sha')!=contract['candidate']['controller_sha']
            or binding.get('inventory_sha256')!=contract['writer_inventory_sha256']
            or binding.get('system_identifier')!=contract['database']['system_identifier']):
        raise RuntimeError('schema150_status_journal_binding_changed')
    validate_inventory(_document(root/'provider-inventory.json'),binding)
    # _state validates full semantic ordering in addition to the hash chain.
    _,completed,pending,ready=ProviderMaintenance150(binding,journal,None)._state()
    barrier=root/'provider-barrier.json'
    exists=barrier.exists() or barrier.is_symlink()
    if exists and _document(barrier)!={'binding':binding,
            'preimage_sha256':journal_digest(rows[0]['payload']['preimage'])}:
        raise RuntimeError('schema150_status_barrier_changed')
    cleared='clear_boot_interlock' in completed
    barrier_missing=not exists and bool(completed or pending) and not cleared
    barrier_conflict=barrier_missing or (exists and cleared)
    last=next((r['payload'] for r in reversed(rows) if r['event']=='quiescence'),None)
    if last is not None and (not isinstance(last,dict)
            or type(last.get('schema')) is not int or last['schema'] not in (146,147,148,149,150)
            or last.get('system_identifier')!=binding['system_identifier']):
        raise RuntimeError('schema150_status_recorded_database_invalid')
    return {'capability':'INSPECT','operational_profile_registered':False,
        'authority_issued':False,'mutations_executed':False,
        'journal_verified':True,'completed_steps':completed,'pending_step':pending,
        'private_acceptance_recorded':ready,'persistent_barrier_present':exists,
        'requires_independent_recovery':bool(pending or barrier_conflict),
        'last_recorded_schema':last.get('schema') if last else None,
        'current_database_verified':False,'current_services_verified':False,
        'status':'FAIL' if barrier_conflict else 'PARTIAL'}
