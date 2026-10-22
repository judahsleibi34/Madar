"""Fresh admission of a completed NORMAL continuation to one schema upgrade.

The provider record remains historical data. An immutable root receipt and a
fresh systemd credential are both required; merely finding a NORMAL flag, an old
completion, or an agent-written assessment cannot open the ordinary deploy path.
This module does not issue credentials, install controllers or grant writes.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re

from deployment.lib.control_plane_upgrade_authorization import require_upgrade_authorization
from deployment.lib.completed_normal_profile import profile, LEGACY, MANUAL, APPLICATION, COMMERCIAL, FENCED, OUTBOX, DELETION, RECONCILED

OPERATION = "completed-normal-schema115-136-upgrade"
ADMISSIONS = Path("/var/lib/madar-control-plane/upgrades/completed-normal-admissions")
AUTHORITY_DESTINATION = "/run/madar/business-write-authority"
HISTORICAL_NAMES = (
    "authorization.json", "plan.json", "events.jsonl", "normal-completion.json", "normal-publication.json",
    "normal-acceptance.json", "post-cutover-backup.json", "installed-controller.json", "worker-owner.json",
    "candidate-identities.json", "candidate-contract.json", "runtime-dependencies.json",
    "fenced-local-reconciliation.json", "retained-writer-fence.json", "write-boundary.json",
    "boot-installation.json", "fallback-listener-installation.json",
    "worker-start-notification.json", "worker-start-calendar-sync.json", "worker-start-data-deletion.json",
)
COMPATIBLE_HISTORICAL_NAMES = (
    'operator-authorization.json', 'admission.json', 'normal-completion.json',
    'normal-publication.json', 'target-normal-publication.json',
    'post-migration-backup.json', 'controller-installation-intent.json',
    'controller-installation.json', 'boot-installation.json', 'boot-preimages.json',
    'candidate-runtime.json', 'migration-intent.json', 'migration-completion.json',
    'migration-execution.json', 'migration-manifest.json',
    'migration-customer-preservation.json',
)
APPLICATION_HISTORICAL_NAMES = tuple(
    name for name in COMPATIBLE_HISTORICAL_NAMES if not name.startswith('migration-')
)


def encoded(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def digest(value: dict) -> str:
    return hashlib.sha256(encoded(value)).hexdigest()


def prepared_path(contract, state_root, *, preparation150=False):
    """Fresh admission cannot adopt an earlier candidate's mutable record."""
    if preparation150:validate_provider_preparation(contract)
    else:validate_contract(contract)
    return Path(state_root)/('prepared-completed-normal-'+digest(contract)+'.json')


def validate_contract(value: dict) -> None:
    if not isinstance(value, dict):
        raise RuntimeError("completed_normal_admission_contract_invalid")
    _validate_contract(value, profile(value))


def validate_provider_preparation150(value: dict) -> None:
    """Pure validation only; does not register or admit the150 operation."""
    from deployment.lib.completed_normal_profile import DELETION
    if (not isinstance(value, dict) or value.get("operation") != DELETION.operation
            or type(value.get("version")) is not int or value["version"] != DELETION.version):
        raise RuntimeError("schema150_provider_contract_invalid")
    _validate_contract(value, DELETION)


def validate_provider_preparation(contract):
    """Validate either exact maintenance preparation; never admit execution."""
    from deployment.lib.completed_normal_profile import provider_preparation_profile
    selected = provider_preparation_profile(contract)
    _validate_contract(contract, selected)
    if selected is RECONCILED:
        from deployment.lib.schema160_release import MANIFEST_SHA256
        if contract['migration_manifest_sha256'] != MANIFEST_SHA256:
            raise RuntimeError('schema160_migration_manifest_changed')
    return selected


def _validate_contract(value: dict, selected) -> None:
    if not isinstance(value, dict):
        raise RuntimeError("completed_normal_admission_contract_invalid")
    if set(value) != {
        "version", "operation", "source_roles", "origin", "candidate",
        "historical_files", "database", "migration_manifest_sha256",
        "rehearsal_sha256", "plan_sha256", "provider_record_sha256", "resources",
        "customer_table_roots_sha256", "customer_identity_roots_sha256",
    } | ({"provider_maintenance_sha256", "writer_inventory_sha256"} if selected in (OUTBOX, DELETION, RECONCILED) else set()) | ({"notification_cutover_sha256"} if selected in (FENCED, OUTBOX, DELETION, RECONCILED) else set()) | ({"database_structure_sha256"} if selected in (COMMERCIAL,FENCED,OUTBOX,DELETION,RECONCILED) else set()):
        raise RuntimeError("completed_normal_admission_contract_invalid")
    if selected in (FENCED, OUTBOX, DELETION, RECONCILED) and not re.fullmatch("[0-9a-f]{64}",str(value.get("notification_cutover_sha256"))):
        raise RuntimeError("schema148_cutover_binding_invalid")
    if selected in (OUTBOX, DELETION, RECONCILED) and any(not re.fullmatch('[0-9a-f]{64}', str(value.get(key)))
            for key in ('provider_maintenance_sha256','writer_inventory_sha256')):
        raise RuntimeError('schema149_provider_binding_invalid')
    roles = value["source_roles"]
    role_keys = ({'application_sha', 'controller_sha', 'completion_root', 'original_plan_sha256', 'completion_sha256'}
        if selected is LEGACY else {'application_sha', 'controller_sha', 'completion_root', 'completion_sha256', 'completed_compatible_upgrade', 'schema'})
    if not isinstance(roles, dict) or set(roles) != role_keys:
        raise RuntimeError("completed_normal_admission_origin_invalid")
    from deployment.lib.active_recovery_resumption import ROOT
    origin_root = Path(roles['completion_root'])
    valid_root = (roles['completion_root'] == str(ROOT / roles['original_plan_sha256'])
        if selected is LEGACY else origin_root.parent == ADMISSIONS
        and re.fullmatch('[0-9a-f]{64}', origin_root.name)
        and roles['completed_compatible_upgrade'] is True and type(roles['schema']) is int and roles['schema'] == selected.source)
    if not valid_root:
        raise RuntimeError("completed_normal_admission_origin_invalid")
    origin, candidate, database = value["origin"], value["candidate"], value["database"]
    if (not isinstance(origin, dict) or set(origin) != {"slot", "images", "worker_generation", "write_contract_digest"}
            or origin["slot"] not in {"blue", "green"}
            or not isinstance(candidate, dict) or set(candidate) != {
                "source_sha", "controller_sha", "controller_tree_sha256", "images", "redis_image", "slot", "compatible_min", "compatible_max"}
            or candidate["slot"] not in {"blue", "green"} or candidate["slot"] == origin["slot"]
            or type(candidate["compatible_min"]) is not int or candidate["compatible_min"] != selected.minimum
            or type(candidate["compatible_max"]) is not int or candidate["compatible_max"] != selected.target
            or not isinstance(database, dict) or set(database) != {
                "container_id", "image", "system_identifier", "schema", "spec_sha256", "network_name", "network_id", "backup_configuration_sha256"}
            or type(database["schema"]) is not int or database["schema"] != selected.source
            or not re.fullmatch(r"[0-9]+", str(database["system_identifier"]))):
        raise RuntimeError("completed_normal_admission_runtime_invalid")
    for images in (origin["images"], candidate["images"]):
        if not isinstance(images, dict) or set(images) != {"backend", "frontend"} or any(
                not re.fullmatch(r"sha256:[0-9a-f]{64}", str(v)) for v in images.values()):
            raise RuntimeError("completed_normal_admission_images_invalid")
    if not re.fullmatch('sha256:[0-9a-f]{64}',str(candidate['redis_image'])):
        raise RuntimeError('completed_normal_admission_redis_invalid')
    for sha in (roles["application_sha"], roles["controller_sha"], candidate["source_sha"], candidate["controller_sha"]):
        if not re.fullmatch(r"[0-9a-f]{40}", str(sha)):
            raise RuntimeError("completed_normal_admission_source_invalid")
    hashes = [origin_root.name, roles["completion_sha256"], origin["worker_generation"], origin["write_contract_digest"],
              database["container_id"], value["migration_manifest_sha256"], value["rehearsal_sha256"], value["plan_sha256"],
              database['spec_sha256'], database['network_id'], database['backup_configuration_sha256'],
              value["provider_record_sha256"], candidate["controller_tree_sha256"],
              value['customer_table_roots_sha256'],value['customer_identity_roots_sha256']]
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", str(database["image"])):
        raise RuntimeError("completed_normal_admission_database_invalid")
    if database['network_name']!='madar-local-supabase_default':
        raise RuntimeError('completed_normal_admission_database_network_invalid')
    files = value["historical_files"]
    if not isinstance(files, dict) or not files:
        raise RuntimeError("completed_normal_admission_history_missing")
    names = HISTORICAL_NAMES if selected is LEGACY else COMPATIBLE_HISTORICAL_NAMES
    required = {str(origin_root / name) for name in names}
    # These are historical protected records only, never arbitrary executable or
    # operator-selected paths. The retained provider record is checked separately.
    application_required = {str(origin_root / name) for name in APPLICATION_HISTORICAL_NAMES}
    if set(files) != required and not (selected in (APPLICATION, COMMERCIAL, FENCED, OUTBOX, DELETION, RECONCILED) and set(files) == application_required):
        raise RuntimeError("completed_normal_admission_history_invalid")
    if selected in (COMMERCIAL,FENCED,OUTBOX,DELETION,RECONCILED):hashes.append(value["database_structure_sha256"])
    hashes.extend(files.values())
    if any(not re.fullmatch(r"[0-9a-f]{64}", str(v)) for v in hashes):
        raise RuntimeError("completed_normal_admission_digest_invalid")
    resources=value['resources']
    if not isinstance(resources,dict) or set(resources)!={'blue','green'}:
        raise RuntimeError('completed_normal_admission_resources_invalid')
    from deployment.lib.completed_normal_resources import NETWORK_KEYS
    networks=[]
    for item in resources.values():
        if (not isinstance(item,dict) or set(item)!={'subnets','retired_port_declarations'}
                or not isinstance(item['subnets'],dict) or set(item['subnets'])!=set(NETWORK_KEYS)
                or not isinstance(item['retired_port_declarations'],dict)):
            raise RuntimeError('completed_normal_admission_resources_invalid')
        try:
            for raw in item['subnets'].values():
                n=ipaddress.ip_network(raw,strict=True)
                if n.version!=4 or not n.is_private or n.prefixlen!=24: raise ValueError()
                networks.append(n)
        except (ValueError,TypeError):
            raise RuntimeError('completed_normal_admission_subnet_invalid') from None
        for name,binding in item['retired_port_declarations'].items():
            if (not re.fullmatch(r'madar-[a-zA-Z0-9_.-]+',name)
                    or not isinstance(binding,dict) or set(binding)!={'container_id','image_id','spec_sha256'}
                    or not re.fullmatch('[0-9a-f]{64}',str(binding['container_id']))
                    or not re.fullmatch('[0-9a-f]{64}',str(binding['spec_sha256']))
                    or not re.fullmatch('sha256:[0-9a-f]{64}',str(binding['image_id']))):
                raise RuntimeError('completed_normal_admission_retained_resource_invalid')
    if any(a.overlaps(b) for i,a in enumerate(networks) for b in networks[i+1:]):
        raise RuntimeError('completed_normal_admission_subnet_overlap')


def require_fresh_authorization(contract: dict) -> None:
    validate_contract(contract)
    selected = profile(contract)
    require_upgrade_authorization(
        contract["candidate"]["controller_sha"], required_operation=selected.operation,
        required_schema=selected.source, required_context_digest=digest(contract), require_rehearsal=True,
    )
    # The shared credential validator compares interlock and credential. Also
    # bind the rehearsal to this contract, not just to each other.
    from deployment.lib.control_plane_upgrade_authorization import UPGRADE_INTERLOCK
    state = json.loads(UPGRADE_INTERLOCK.read_text())
    if (state.get("rehearsal_sha256") != contract["rehearsal_sha256"]
            or state.get("status") != "authorized_cycle"):
        raise RuntimeError("completed_normal_admission_rehearsal_changed")


def credential_witness(name: str, hash_key: str) -> dict:
    """Read a root-hash-bound witness through the existing credential boundary.

    History stays 0700. The root issuer copies only nonsecret measured admission
    metadata and a grant witness into LoadCredential, binding its exact canonical
    hash in the protected public interlock. A caller-written JSON is insufficient.
    This never copies historical bearer credentials or exposes configuration.
    """
    from deployment.lib.control_plane_upgrade_authorization import UPGRADE_INTERLOCK
    from deployment.lib.provider_recovery_runtime import protected
    directory=os.getenv('CREDENTIALS_DIRECTORY','')
    if not directory.startswith('/'):
        raise RuntimeError('completed_normal_credential_witness_missing')
    path=Path(directory)/'madar-control-plane-upgrade'
    if path.is_symlink() or not path.is_file():
        raise RuntimeError('completed_normal_credential_witness_missing')
    value=json.loads(path.read_text()).get(name)
    state=json.loads(protected(UPGRADE_INTERLOCK).read_text())
    if (not isinstance(value,dict) or not re.fullmatch('[0-9a-f]{64}',str(state.get(hash_key,'')))
            or digest(value)!=state[hash_key]):
        raise RuntimeError('completed_normal_credential_witness_changed')
    return value


def verify_history(contract: dict, *, _visited=frozenset()) -> None:
    from deployment.lib.provider_recovery_runtime import protected, file_digest
    for name, expected in contract["historical_files"].items():
        nonsecret_admission=(profile(contract) is not LEGACY and Path(name)==Path(contract['source_roles']['completion_root'])/'admission.json')
        if file_digest(protected(Path(name), private=not nonsecret_admission)) != expected:
            raise RuntimeError("completed_normal_admission_historical_evidence_changed")
    root = Path(contract['source_roles']['completion_root'])
    if (profile(contract) in (APPLICATION, COMMERCIAL, FENCED, OUTBOX) and set(contract['historical_files']) ==
            {str(root / name) for name in APPLICATION_HISTORICAL_NAMES}):
        # A no-SQL receipt set is valid only for an actually completed no-SQL
        # origin. It cannot hide missing migration evidence from another profile.
        if root in _visited or len(_visited) >= 32:
            raise RuntimeError('completed_normal_application_history_cycle')
        admission = json.loads(protected(root/'admission.json').read_text())
        previous = admission.get('contract')
        validate_contract(previous)
        completion = json.loads(protected(root/'normal-completion.json',private=True).read_text())
        roles = contract['source_roles'];candidate = previous['candidate']
        if (profile(previous) is not APPLICATION or admission.get('operation') != APPLICATION.operation
                or digest(previous) != root.name
                or candidate['source_sha'] != roles['application_sha']
                or candidate['controller_sha'] != roles['controller_sha']
                or candidate['images'] != contract['origin']['images']
                or completion.get('operation') != APPLICATION.operation
                or completion.get('context_sha256') != root.name or completion.get('mode') != 'NORMAL'
                or completion.get('schema') != contract['database']['schema']
                or completion.get('application_sha') != roles['application_sha']
                or completion.get('controller_sha') != roles['controller_sha']
                or completion.get('images') != candidate['images']
                or completion.get('customer_database_restored') is not False
                or completion.get('sql_executed') is not False
                or file_digest(root/'normal-completion.json') != roles['completion_sha256']):
            raise RuntimeError('completed_normal_application_origin_history_invalid')
        verify_history(previous, _visited=_visited | {root})


def provider_record_metadata(state_root: Path) -> dict:
    """Nonsecret identity of the historical root-private record.

    The deployment user can stat this file but must not read its contents.
    Nanosecond change times and inode/device prevent replacing a root-issued
    measurement with a different file while its child credential is active.
    """
    from deployment.lib.provider_recovery_runtime import readonly_configuration
    path = readonly_configuration(Path(state_root) / 'provider-recovery.json', private=True)
    st = path.stat()
    if st.st_uid != 0 or st.st_mode & 0o077:
        raise RuntimeError('completed_normal_provider_record_identity_invalid')
    return {'path': str(path), 'device': st.st_dev, 'inode': st.st_ino,
            'size': st.st_size, 'mtime_ns': st.st_mtime_ns, 'ctime_ns': st.st_ctime_ns,
            'uid': st.st_uid, 'gid': st.st_gid, 'mode': st.st_mode & 0o7777}


def measure_provider_record(state_root: Path, expected_sha256: str) -> dict:
    """Root remeasures before issuing every fresh child credential."""
    from deployment.lib.provider_recovery_runtime import file_digest
    if os.geteuid() != 0:
        raise RuntimeError('completed_normal_provider_record_root_required')
    before = provider_record_metadata(state_root)
    actual = file_digest(Path(before['path']))
    if actual != expected_sha256 or provider_record_metadata(state_root) != before:
        raise RuntimeError('completed_normal_admission_provider_record_changed')
    return dict(before, sha256=actual)


def require_candidate_authority(contract: dict, *, mode: str | None = None, admissions: Path = ADMISSIONS) -> dict:
    """Read the root-issued v2 grant; no caller/environment can issue one."""
    from deployment.lib.provider_recovery_runtime import protected
    validate_contract(contract)
    selected = profile(contract)
    if os.geteuid()==0:
        value = json.loads(protected(admissions / digest(contract) / "write-authority/authority.json").read_text())
    else:
        require_fresh_authorization(contract)
        value=credential_witness('candidate_authority','candidate_authority_sha256')
    if (not isinstance(value, dict) or set(value) != {
            "version", "schema", "release_sha", "contract_digest", "mode", "compatible_min", "compatible_max"}
            or type(value["version"]) is not int or value["version"] != 2
            or not selected.supports(value["schema"])
            or type(value["compatible_min"]) is not int or value["compatible_min"] != selected.minimum
            or type(value["compatible_max"]) is not int or value["compatible_max"] != selected.target
            or value["release_sha"] != contract["candidate"]["source_sha"]
            or value["contract_digest"] != digest(contract)
            or selected.maintenance and value.get('mode')=='NORMAL' and value['schema']!=selected.target
            or value["mode"] not in {"READ_ONLY", "NORMAL"} or mode is not None and value["mode"] != mode):
        raise RuntimeError("completed_normal_candidate_authority_changed")
    return value


def publish_admission(contract: dict, operations, state_root: Path, *, admissions: Path = ADMISSIONS) -> Path:
    """Root effect for a *freshly* authorized driver, before controller changes.

    The caller holds the deployment lock; the independent completed runtime
    verifier runs here, not in an agent-provided PASS packet. The planned origin
    and database identity must match its actual observations immediately before
    the immutable receipt is created. Existing receipts are never overwritten.
    """
    from deployment.lib.completed_normal_baseline import attest_runtime
    from deployment.lib.provider_recovery_runtime import readonly_configuration, protected
    if os.geteuid() != 0:
        raise RuntimeError("completed_normal_admission_root_required")
    require_fresh_authorization(contract)
    selected = profile(contract)
    state = json.loads(readonly_configuration(Path(state_root) / "state.json", private=True).read_text())
    if selected is LEGACY:
        roles = attest_runtime(operations, state)
    else:
        from deployment.lib.completed_normal_baseline import attest_compatible_runtime
        roles = attest_compatible_runtime(operations, state, operations.repository_head(), operations.installed_sha())
    known = state["known_good_release"]
    grant=json.loads(protected(Path(roles['completion_root'])/'write-authority/authority.json').read_text())
    origin_images = known['images'] if selected is LEGACY else {
        key: 'sha256:' + str(known['images'][key]).split('sha256:')[-1] for key in ('backend', 'frontend')}
    actual_origin = {"slot": state["active_slot"], "images": origin_images, "worker_generation": known["worker_generation"],
                     "write_contract_digest":grant.get('contract_digest')}
    if roles != contract["source_roles"] or actual_origin != contract["origin"]:
        raise RuntimeError("completed_normal_admission_live_origin_changed")
    verify_history(contract)
    from deployment.lib.completed_normal_database import customer_baseline
    from deployment.lib.emergency_routing_repair import Runtime
    baseline=customer_baseline(contract,Runtime())
    from deployment.lib.completed_normal_database import verify_preparation_baseline
    try:verify_preparation_baseline(contract,Runtime(),baseline)
    except RuntimeError as error:
        if str(error)=='completed_upgrade_current_customer_data_changed':
            raise RuntimeError('completed_normal_admission_current_customer_data_changed') from None
        raise
    db = contract["database"]
    result = operations.command("completed_normal_admission_database_identity", [
        "docker", "inspect", db["container_id"]])
    rows = json.loads(result.stdout)
    if (len(rows) != 1 or rows[0]["Id"] != db["container_id"] or rows[0]["Image"] != db["image"]
            or not rows[0]["State"]["Running"] or rows[0]["State"].get("Health", {}).get("Status") != "healthy"):
        raise RuntimeError("completed_normal_admission_database_changed")
    result = operations.command("completed_normal_admission_database_schema", [
        "docker", "exec", db["container_id"], "psql", "-XAt", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres",
        "-c", "BEGIN READ ONLY; SELECT system_identifier::text || ':' || schema_version::text FROM pg_control_system(), public.application_schema_state WHERE contract_key='core'; COMMIT;",
    ])
    # -q suppresses transaction tags on some client versions; accept neither
    # ambiguous rows nor another schema. No credentials or customer rows emitted.
    if [line for line in result.stdout.splitlines() if line not in {"BEGIN", "COMMIT"}] != [db["system_identifier"] + ':' + str(selected.source)]:
        raise RuntimeError("completed_normal_admission_database_changed")
    provider = Path(state_root) / "provider-recovery.json"
    from deployment.lib.provider_recovery_runtime import readonly_configuration as read_config
    provider_bytes = read_config(provider, private=True).read_bytes()
    record = json.loads(provider_bytes)
    if (record.get("profile") != "provider402-signin" or record.get("phase") != "local_rollback_active"
            or hashlib.sha256(provider_bytes).hexdigest() != contract["provider_record_sha256"]):
        raise RuntimeError("completed_normal_admission_provider_state_changed")
    admissions.mkdir(mode=0o755, parents=True, exist_ok=True)
    # Do not create a root-issued receipt inside an operator-writable parent.
    for directory in (admissions, *admissions.parents):
        stat = directory.lstat()
        if directory.is_symlink() or stat.st_uid != 0 or stat.st_mode & 0o022:
            raise RuntimeError("completed_normal_admission_directory_untrusted")
    root = admissions / digest(contract)
    root.mkdir(mode=0o755, parents=True, exist_ok=False)
    from deployment.lib.emergency_routing_repair import exclusive
    receipt = {"version": 1, "operation": selected.operation, "contract": contract,
               "provider_record_sha256": hashlib.sha256(provider_bytes).hexdigest(),
               "observed_at": datetime.now(timezone.utc).isoformat(),
               "database_restored": False, "historical_authorization_reused": False}
    exclusive(root / "admission.json", encoded(receipt))
    exclusive(root / 'admitted-customer-baseline.json',encoded(baseline))
    os.chmod(root / "admission.json", 0o444)
    exclusive(root / "events.jsonl", (json.dumps({"operation": selected.operation, "phase": "admitted", "context_sha256": digest(contract)}, sort_keys=True) + "\n").encode())
    authority = root / "write-authority"
    authority.mkdir(mode=0o755)
    # The root coordinator runs with UMask=0077. Set the nonsecret mounted
    # directory explicitly; mkdir(mode=0755) alone produces unreadable0700.
    authority.chmod(0o755)
    exclusive(authority / "authority.json", encoded({
        "version": 2, "schema": selected.source, "release_sha": contract["candidate"]["source_sha"],
        "contract_digest": digest(contract), "mode": "READ_ONLY", "compatible_min": selected.minimum, "compatible_max": selected.target,
    }))
    os.chmod(authority / "authority.json", 0o644)
    return root


def require_admission(state_root: Path, application_sha: str | None, *, admissions: Path = ADMISSIONS) -> dict:
    """Credential-bound admission at every real deploy and migration entrypoint."""
    from deployment.lib.control_plane_upgrade_authorization import UPGRADE_INTERLOCK
    from deployment.lib.provider_recovery_runtime import protected, readonly_configuration, file_digest
    if not UPGRADE_INTERLOCK.exists():
        raise RuntimeError("provider_recovery_requires_separate_operator_exit")
    interlock = json.loads(protected(UPGRADE_INTERLOCK).read_text())
    context = str(interlock.get("context_sha256", ""))
    if interlock.get("operation") not in {LEGACY.operation, MANUAL.operation, APPLICATION.operation, COMMERCIAL.operation, FENCED.operation, OUTBOX.operation} or not re.fullmatch(r"[0-9a-f]{64}", context):
        raise RuntimeError("provider_recovery_requires_separate_operator_exit")
    receipt = credential_witness('completed_normal_admission','admission_sha256')
    contract = receipt.get("contract")
    validate_contract(contract)
    selected = profile(contract)
    if (set(receipt) != {"version", "operation", "contract", "provider_record_sha256", "observed_at", "database_restored", "historical_authorization_reused"}
            or receipt["version"] != 1 or receipt["operation"] != selected.operation or interlock['operation'] != selected.operation or digest(contract) != context
            or receipt["database_restored"] is not False or receipt["historical_authorization_reused"] is not False
            or application_sha not in {None, contract["candidate"]["source_sha"]}):
        raise RuntimeError("completed_normal_admission_binding_changed")
    require_fresh_authorization(contract)
    provider = credential_witness('provider_record_witness', 'provider_record_witness_sha256')
    if (receipt["provider_record_sha256"] != contract["provider_record_sha256"]
            or provider != dict(provider_record_metadata(state_root), sha256=contract['provider_record_sha256'])):
        raise RuntimeError("completed_normal_admission_provider_record_changed")
    # The root coordinator remeasures private historical evidence at each
    # privileged boundary. The madar child sees only this immutable root-issued
    # admission and the fresh scoped credential, never historical private files.
    from deployment.lib.active_recovery_inputs import INPUTS, controller_tree_digest
    if (protected(INPUTS["controller"]).read_text().strip() != contract["candidate"]["controller_sha"]
            or controller_tree_digest() != contract["candidate"]["controller_tree_sha256"]):
        raise RuntimeError("completed_normal_admission_installed_controller_changed")
    state = json.loads(readonly_configuration(Path(state_root) / "state.json", private=True).read_text())
    known = state.get("known_good_release") or {}
    candidate = contract["candidate"]
    old = contract["source_roles"]["application_sha"]
    expected_slot = contract["origin"]["slot"] if known.get("sha") == old else candidate["slot"]
    expected_images = contract["origin"]["images"] if known.get("sha") == old else candidate["images"]
    # Ordinary records include the backend as a separately pinned worker image
    # and image-reference strings; normalize only the exact SHA-256 suffix.
    images = {k: ("sha256:" + str(v).split("sha256:")[-1]) for k, v in known.get("images", {}).items() if k in {"backend", "frontend"}}
    if (known.get("sha") not in {old, candidate["source_sha"]} or known.get("slot") != expected_slot
            or state.get("active_slot") != expected_slot or images != expected_images
            or not selected.supports(known.get('schema'))
            or known.get('sha') == old and known['schema'] != selected.source):
        raise RuntimeError("completed_normal_admission_release_changed")
    pending = state.get("in_progress_release")
    if pending and (pending.get("release_sha") != candidate["source_sha"] or pending.get("candidate_slot") != candidate["slot"]):
        raise RuntimeError("completed_normal_admission_pending_release_changed")
    return contract
