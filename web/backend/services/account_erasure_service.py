"""Explicit account actions and bounded protocol3 server-resource erasure.

Customer admission remains disabled in candidate167. The same service-only
enrollment/worker functions are exercised by disposable integration.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import time

from fastapi import HTTPException

from services.account_work_fence import AccountWorkBusy, account_lock, publish_hold, finish_account_fence
from services.upload_config import get_data_upload_dir, get_private_charts_dir, get_public_uploads_dir


MAX_FILES = 20000
MAX_FILE_BYTES = 250_000_000
MAX_REQUEST_SECONDS = 60


class LifecycleBlocked(RuntimeError):
    pass


class LifecycleRetry(RuntimeError):
    pass


def action_status(row):
    return {"request_id":row["id"],"action":row["action"],"state":row["state"],
        "recovery_deadline":row.get("recovery_deadline"),"eligible_at":row.get("eligible_at"),
        "irreversible_at":row.get("irreversible_at"),"completed_at":row.get("completed_at"),
        "error_code":row.get("error_code"),"completion_boundary":"server_controlled",
        "offline_device_erasure":False}


def capability(client):
    try:
        value = client.rpc("account_lifecycle_capability167", {}).execute().data
    except Exception:
        value = None
    if not isinstance(value, dict) or type(value.get("protocol")) is not int or value["protocol"] != 3 \
            or value.get("deactivate_recovery_hours") != 2160 or value.get("delete_recovery_hours") != 0 \
            or value.get("completion_boundary") != "server_controlled" \
            or value.get("admission") != {"deactivate":False,"delete":False}:
        raise HTTPException(status_code=503, detail="Account lifecycle is unavailable.")
    return value


def storage_binding():
    result={}
    for name,path in _root_paths().items():
        path.mkdir(parents=True,exist_ok=True,mode=0o700)
        descriptor=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            info=os.fstat(descriptor)
            result[name]={"path":str(path),"device":info.st_dev,"inode":info.st_ino}
        finally:os.close(descriptor)
    from services.account_restore_boundary import floor_binding
    result["restore_floor"]=floor_binding()
    return result


def enroll_authorized(*, user_id, actor_id, action, client, request=None):
    """Trusted backend enrollment; SQL independently authorizes the actor.

    EX serializes enrollment with all participating writers before the SQL
    freeze/session revocation. A busy account is refused without accepting a
    partially frozen action. No caller-supplied deadline is accepted.
    """
    capability(client)
    if action not in {"deactivate","delete"}:
        raise HTTPException(status_code=422, detail="An explicit account action is required.")
    users=client.table("users").select("id,tenant_id,email").eq("id",int(user_id)).limit(1).execute().data
    if not users: raise HTTPException(status_code=404, detail="Account was not found.")
    if request is not None:
        from services.account_work_fence import release_request_scope
        release_request_scope(request,users[0]["tenant_id"],user_id)
    with account_lock(users[0]["tenant_id"],user_id,exclusive=True,client=client) as marker:
        existed=marker.exists()
        if not existed: publish_hold(marker,{"state":"enrolling"})
        try:
            from services.audit_service import hash_audit_identifier
            binding=storage_binding();binding["identity_sha256"]=hash_audit_identifier(users[0]["email"])
            row=client.rpc("create_account_action167",{"p_user_id":int(user_id),"p_actor_id":int(actor_id),"p_action":action,"p_storage_binding":binding}).execute().data
        except Exception:
            if not existed: marker.unlink(missing_ok=True)
            raise
        publish_hold(marker,{"request_id":row["id"],"action":row["action"]})
        return row


def request_action(*, user_id, actor_id, action, client, request=None):
    value=capability(client)
    if action not in {"deactivate","delete"}: raise HTTPException(status_code=422,detail="An explicit account action is required.")
    if value["admission"][action] is not True:
        raise HTTPException(status_code=503,detail={"code":"account_lifecycle_acceptance_required","message":"This account action is currently unavailable. Contact support."})
    return enroll_authorized(user_id=user_id,actor_id=actor_id,action=action,client=client,request=request)


def reactivate(*, request_id, actor_id, client):
    capability(client)
    rows=client.table("account_lifecycles167").select("id,subject_id,tenant_id").eq("id",request_id).limit(1).execute().data
    if not rows or not rows[0].get("subject_id"): raise HTTPException(status_code=404,detail="Account action was not found.")
    with account_lock(rows[0]["tenant_id"],rows[0]["subject_id"],exclusive=True,client=client) as marker:
        result=client.rpc("reactivate_account167",{"p_request_id":request_id,"p_actor_id":int(actor_id)}).execute().data
        marker.unlink(missing_ok=True)
        return result


def require_backend_session(*, auth_id, token, client, request=None, user=None):
    from services.project_dataset_service import schema_version
    version=schema_version(client=client)
    if 146<=version<=166: return
    if version!=167: raise HTTPException(status_code=503,detail="Account session verification is unavailable.")
    if request is not None and user and user.get("tenant_id") is not None:
        from services.account_work_fence import protect_request
        # All authenticated modules, not just Data Analysis. Recheck the live
        # session AFTER acquiring SH to close profile-read/enrollment races.
        protect_request(request,user["tenant_id"],user["id"],client=client)
    try:
        import jwt
        # The provider already verified this credential. It is decoded ONLY to
        # bind its session claim to the independently verified provider user ID.
        session_id=jwt.decode(token,options={"verify_signature":False}).get("session_id")
        if not session_id: raise ValueError()
        allowed=client.rpc("account_session_allowed167",{"p_auth_id":str(auth_id),"p_session_id":str(session_id)}).execute().data
    except Exception:
        allowed=False
    if allowed is not True: raise HTTPException(status_code=401,detail="This session is no longer active.")


def _args(claim):
    return {"p_request_id":claim["id"],"p_token":claim["lease_token"],"p_generation":claim["generation"]}


def _rpc(client,name,claim,**values):
    return client.rpc(name,{**_args(claim),**values}).execute().data


def _transition(client,claim,action,resource=None,code=None):
    return _rpc(client,"account_erasure_transition167",claim,p_action=action,p_resource_id=resource,p_code=code)


def _parts(relative):
    if not isinstance(relative,str) or "\\" in relative or "\x00" in relative:
        raise LifecycleBlocked("account_file_scope_invalid")
    parts=PurePosixPath(relative).parts
    if not parts or relative.startswith("/") or any(p in {".","..",""} for p in relative.split("/")):
        raise LifecycleBlocked("account_file_scope_invalid")
    return parts


@contextmanager
def _parent(root,relative):
    parts=_parts(relative);fds=[]
    try:
        descriptor=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);fds.append(descriptor)
        for part in parts[:-1]:
            descriptor=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=descriptor);fds.append(descriptor)
        yield descriptor,parts[-1]
    finally:
        for descriptor in reversed(fds): os.close(descriptor)


def _fingerprint(root,relative,deadline=None):
    with _parent(root,relative) as (parent,name):
        descriptor=os.open(name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=parent)
        try:
            before=os.fstat(descriptor)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>MAX_FILE_BYTES:
                raise LifecycleBlocked("account_file_identity_unsupported")
            digest=hashlib.sha256()
            while chunk:=os.read(descriptor,1024*1024):
                if deadline is not None and time.monotonic()>deadline: raise LifecycleBlocked("account_scan_budget")
                digest.update(chunk)
            after=os.fstat(descriptor)
            if (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino):
                raise LifecycleBlocked("account_file_changed")
            return {"size":before.st_size,"sha256":digest.hexdigest(),"inode":before.st_ino,"device":before.st_dev}
        finally: os.close(descriptor)


def _resource_rows(client,claim):
    rows=[];total=None
    while total is None or len(rows)<total:
        response=client.table("account_lifecycle_resources167").select("*",count="exact").eq("request_id",claim["id"]).order("id").range(len(rows),len(rows)+249).execute()
        if type(response.count) is not int or response.count>MAX_FILES:
            raise LifecycleBlocked("account_inventory_count_unavailable")
        if total is not None and total!=response.count:raise LifecycleBlocked("account_inventory_changed")
        total=response.count
        if not response.data and len(rows)<total:raise LifecycleBlocked("account_inventory_truncated")
        rows.extend(response.data)
    return rows


def _roots(claim,resources):
    tenant,user=int(claim["tenant_id"]),int(claim["subject_id"])
    result=[("uploads",f"tenant_{tenant}/user_{user}"),("charts",f"tenant_{tenant}/user_{user}"),
            ("uploads",f".parquet_cache/tenant_{tenant}/user_{user}")]
    for row in resources:
        identity=row["identity"]
        if row["kind"]=="storage" and identity.get("backend")=="supabase_private":
            digest=hashlib.sha256((identity["bucket"]+"/"+identity["provider_key"]).encode()).hexdigest()
            result.append(("uploads",f".immutable_scratch/tenant_{tenant}/object_{digest}"))
        if row["kind"]=="report":
            report=row["identity"]["id"]
            from uuid import UUID
            if str(UUID(report))!=report: raise LifecycleBlocked("account_report_scope_invalid")
            result.extend([("charts",f"reports/tenant_{tenant}/{report}"),("charts",f".report-tmp/tenant_{tenant}/{report}")])
    return result


def _remove_empty_roots(claim,resources):
    roots=_root_paths()
    for kind,relative in _roots(claim,resources):
        root=roots[kind]
        if not root.exists():continue
        # Traversal has already established absence of files and rejected links.
        # Rmdir is intentionally non-recursive: unexpected content must refuse.
        paths=[]
        try:
            with _parent(root,relative) as (parent,name):
                start=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent)
        except FileNotFoundError:continue
        stack=[(start,relative)]
        try:
            while stack:
                fd,prefix=stack.pop();paths.append(prefix)
                try:
                    for name in os.listdir(fd):
                        info=os.stat(name,dir_fd=fd,follow_symlinks=False)
                        if not stat.S_ISDIR(info.st_mode):raise LifecycleBlocked("account_private_files_remain")
                        stack.append((os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd),prefix+"/"+name))
                finally:os.close(fd)
        finally:
            for fd,_ in stack:os.close(fd)
        for path in sorted(paths,key=lambda p:p.count('/'),reverse=True):
            with _parent(root,path) as (parent,name):os.rmdir(name,dir_fd=parent)


def _root_paths():
    return {"uploads":get_data_upload_dir(),"charts":get_private_charts_dir(),"public":get_public_uploads_dir()}


def _scan(claim,resources,deadline=None):
    """Bounded descriptor traversal; no symlinks, hardlinks or path following."""
    roots=_root_paths();found=[];seen=0
    for kind,relative in _roots(claim,resources):
        root=roots[kind]
        if not root.exists(): continue
        try:
            with _parent(root,relative) as (parent,name):
                start=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent)
        except FileNotFoundError: continue
        stack=[(start,relative)]
        try:
            while stack:
                descriptor,prefix=stack.pop()
                try:
                    for name in os.listdir(descriptor):
                        if deadline is not None and time.monotonic()>deadline: raise LifecycleBlocked("account_scan_budget")
                        seen+=1
                        if seen>MAX_FILES: raise LifecycleBlocked("account_inventory_limit")
                        path=prefix+"/"+name
                        info=os.stat(name,dir_fd=descriptor,follow_symlinks=False)
                        if stat.S_ISLNK(info.st_mode): raise LifecycleBlocked("account_file_symlink_refused")
                        if stat.S_ISDIR(info.st_mode):
                            stack.append((os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=descriptor),path))
                        elif stat.S_ISREG(info.st_mode):
                            found.append({"root":kind,"relative":path,**_fingerprint(root,path,deadline)})
                        else: raise LifecycleBlocked("account_file_identity_unsupported")
                finally: os.close(descriptor)
        finally:
            for descriptor,_ in stack: os.close(descriptor)
    return found


def _storage_provider(identity,claim):
    key=identity.get("provider_key")
    if identity.get("category")=="builder_asset":
        expected=f"tenant_{int(claim['tenant_id'])}/builder_assets/"
        owner=identity.get("owner_user_id",identity.get("user_id"))
        if int(owner or 0)!=int(claim["subject_id"]) or identity.get("backend")!="supabase_builder_private" \
                or identity.get("bucket")!="builder-assets" or not key or not key.startswith(expected):
            raise LifecycleBlocked("account_builder_asset_scope_invalid")
        _parts(key)
        if identity.get("local_relative") is not None and identity["local_relative"]!=key:
            raise LifecycleBlocked("account_builder_asset_scope_invalid")
        return identity["bucket"],key
    if int(identity.get("tenant_id",0))!=int(claim["tenant_id"]) or int(identity.get("user_id",0))!=int(claim["subject_id"]):
        raise LifecycleBlocked("account_multitenant_adapter_required")
    category=identity.get("category")
    if category in {"elearning_assessment","elearning_form","academy_document"}:
        from uuid import UUID
        storage_key=identity.get("storage_key")
        parts=_parts(storage_key)
        tenant=f"tenant_{int(claim['tenant_id'])}"
        if category=="elearning_assessment":
            valid=(identity.get("backend")=="supabase_learning_private"
                and identity.get("bucket")=="elearning-assessment-recordings"
                and key==storage_key and len(parts)==4 and parts[0]=="elearning-assessments"
                and parts[1]==tenant and parts[2].startswith("attempt_") and parts[3].endswith(".wav"))
            try:
                UUID(parts[2][8:]);UUID(parts[3][:-4])
            except (ValueError,IndexError):valid=False
        else:
            parent="response_" if category=="elearning_form" else "application_"
            prefix="elearning-private" if category=="elearning_form" else "academy-private"
            valid=(identity.get("backend")=="supabase_learning_private"
                and identity.get("bucket")=="builder-assets" and key==storage_key
                and len(parts)==4 and parts[0]==prefix and parts[1]==tenant and parts[2].startswith(parent))
            try:
                UUID(parts[2][len(parent):]);UUID(parts[3])
            except (ValueError,IndexError):valid=False
        if not valid:raise LifecycleBlocked("account_learning_storage_scope_invalid")
        return identity["bucket"],key
    if identity.get("backend")=="supabase_private":
        if identity.get("bucket")!="madar-data-immutable" or not key or not key.startswith(f"tenant_{int(claim['tenant_id'])}/dataset/"):
            raise LifecycleBlocked("account_provider_scope_invalid")
        parts=_parts(key)
        from uuid import UUID
        if len(parts)!=4 or str(UUID(parts[2]))!=parts[2] or parts[3] not in {str(identity.get('sha256'))+ext for ext in ('.csv','.xlsx','.xls')}:
            raise LifecycleBlocked("account_provider_scope_invalid")
        return identity["bucket"],key
    if identity.get("category")=="avatar":
        key=identity.get("storage_key")
        if not key or not key.startswith(f"users/{claim['auth_id']}/"): raise LifecycleBlocked("account_provider_scope_invalid")
        _parts(key);return "avatars",key
    if identity.get("category") not in {"dataset","generated_artifact"}:
        raise LifecycleBlocked("account_storage_adapter_required")
    key=identity.get("storage_key")
    _parts(key)
    if not key.startswith(f"tenant_{int(claim['tenant_id'])}/user_{int(claim['subject_id'])}/"):
        raise LifecycleBlocked("account_file_scope_invalid")
    return None


def _provider_present(client,bucket,key):
    from services.data_deletion_service import _provider_object_present, DeletionStepError
    try:return _provider_object_present(client,bucket,key)
    except DeletionStepError:raise LifecycleRetry("account_provider_verification_unavailable") from None


def _auth_present(client,auth_id):
    from services.data_deletion_service import _provider_absent
    try:
        response=client.auth.admin.get_user_by_id(auth_id)
        return bool(getattr(response,"user",None))
    except Exception as error:
        if _provider_absent(error): return False
        raise LifecycleRetry("account_auth_verification_unavailable") from None


def _unlink(identity):
    root=_root_paths()[identity["root"]];relative=identity["relative"]
    try: actual=_fingerprint(root,relative)
    except FileNotFoundError: return
    if any(actual[field]!=identity[field] for field in ("sha256","size","inode","device")):
        raise LifecycleBlocked("account_file_identity_changed")
    with _parent(root,relative) as (parent,name):
        # Fingerprint and unlink beneath the same pinned parent. A final leaf
        # replacement after hashing must also be rejected before unlink.
        info=os.stat(name,dir_fd=parent,follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode) or info.st_ino!=identity["inode"] or info.st_dev!=identity["device"] or info.st_nlink!=1:
            raise LifecycleBlocked("account_file_identity_changed")
        os.unlink(name,dir_fd=parent)


def _absent_file(identity):
    try:
        with _parent(_root_paths()[identity["root"]],identity["relative"]) as (parent,name):
            os.stat(name,dir_fd=parent,follow_symlinks=False)
        return False
    except FileNotFoundError:return True


def _complete_claim(client,claim):
    from services.account_restore_boundary import publish_floor
    epoch=_rpc(client,"reserve_account_restore_epoch167",claim)
    publish_floor(epoch)
    try:return _rpc(client,"complete_account_erasure167",claim,p_restore_epoch=epoch)
    except Exception:
        # A lost HTTP ACK may follow a committed completion transaction. Only
        # that RPC can remove this previously acquired service-only lifecycle
        # row. Both operational rows and the public subject must be absent;
        # errors/missing relations are not interpreted as empty results.
        for table,key,value in (("account_lifecycles167","id",claim["id"]),
                                ("data_deletion_requests","id",claim["id"]),
                                ("users","id",claim["subject_id"])):
            response=client.table(table).select("id",count="exact").eq(key,value).limit(1).execute()
            if response.count!=0 or response.data:raise
        return {"id":claim["id"],"action":claim["action"],"state":"completed",
                "recovery_deadline":None,"eligible_at":claim["eligible_at"]}


def process_claim(claim,*,client):
    capability(client)
    started=time.monotonic()
    try:
        binding=storage_binding()
        if binding!={name:claim["storage_binding"].get(name) for name in binding}:raise LifecycleBlocked("account_storage_binding_mismatch")
        with account_lock(claim["tenant_id"],claim["subject_id"],exclusive=True,client=client) as marker:
            publish_hold(marker,{"request_id":claim["id"],"action":claim["action"]})
            _transition(client,claim,"renew")
            if not claim["database_released"]:
                _rpc(client,"inventory_account_erasure167",claim)
                resources=_resource_rows(client,claim)
                import tempfile
                for prefix in ("madar-immutable-read-*","madar-immutable-verify-*","madar-loopback-read-*","madar-loopback-verify-*"):
                    if next(Path(tempfile.gettempdir()).glob(prefix),None) is not None:
                        raise LifecycleBlocked("account_legacy_scratch_reconciliation_required")
                temporary=get_private_charts_dir()/'.report-tmp'
                if temporary.exists() and any(item.is_file() or item.is_symlink() for item in temporary.iterdir()):
                    raise LifecycleBlocked("account_unattributed_temporary_files")
                # Validate every adapter and file identity BEFORE releasing any
                # immutable metadata. Unsupported scope blocks without erasure.
                for resource in resources:
                    if resource["kind"]=="storage": _storage_provider(resource["identity"],claim)
                files=_scan(claim,resources,started+MAX_REQUEST_SECONDS)
                # Builder cache paths are exact asset identities.  Never scan
                # or erase the tenant-wide Builder directory.
                for resource in resources:
                    identity=resource["identity"]
                    if resource["kind"]=="storage" and identity.get("category")=="builder_asset":
                        relative=identity.get("local_relative")
                        if relative:
                            try:item={"root":"public","relative":relative,**_fingerprint(_root_paths()["public"],relative,started+MAX_REQUEST_SECONDS)}
                            except FileNotFoundError:continue
                            if item["sha256"]!=identity.get("sha256") or item["size"]!=int(identity.get("size_bytes",-1)):
                                raise LifecycleBlocked("account_builder_asset_integrity_failed")
                            files.append(item)
                by_path={(f["root"],f["relative"]):f for f in files}
                for resource in resources:
                    identity=resource["identity"]
                    if resource["kind"]=="storage" and not _storage_provider(identity,claim):
                        root="uploads" if identity["category"]=="dataset" else "charts"
                        item=by_path.get((root,identity["storage_key"]))
                        if item and (item["sha256"]!=identity["sha256"] or item["size"]!=identity["size_bytes"]):
                            raise LifecycleBlocked("account_immutable_integrity_failed")
                for item in files:
                    if time.monotonic()-started>MAX_REQUEST_SECONDS:raise LifecycleBlocked("account_scan_budget")
                    _rpc(client,"register_account_file167",claim,p_key=item["relative"],p_identity=item)
                _transition(client,claim,"renew")
                _rpc(client,"release_account_database167",claim)
            resources=_resource_rows(client,claim)
            if len(resources)>MAX_FILES: raise LifecycleBlocked("account_inventory_limit")
            for resource in resources:
                if time.monotonic()-started>MAX_REQUEST_SECONDS:
                    return _transition(client,claim,"retry",code="account_worker_budget")
                if resource["kind"] in {"auth","report"} or resource["state"]=="verified":continue
                _transition(client,claim,"renew")
                identity=resource["identity"]
                if resource["kind"]=="file":
                    _transition(client,claim,"intent",resource["id"])
                    _unlink(identity)
                    if not _absent_file(identity): raise LifecycleBlocked("account_file_remains")
                else:
                    provider=_storage_provider(identity,claim)
                    if provider:
                        bucket,key=provider
                        present=_provider_present(client,bucket,key)
                        if present and resource["state"] in {"intent","uncertain"}:
                            raise LifecycleBlocked("account_provider_outcome_uncertain")
                        if present:
                            _transition(client,claim,"intent",resource["id"])
                            try: client.storage.from_(bucket).remove([key])
                            except Exception:
                                if _provider_present(client,bucket,key): raise LifecycleBlocked("account_provider_outcome_uncertain")
                            if _provider_present(client,bucket,key): raise LifecycleBlocked("account_provider_object_remains")
                _transition(client,claim,"verified",resource["id"])
            # Independent second traversal, independent provider observations,
            # and DB checks follow removal; never certify from intent/ack alone.
            if _scan(claim,resources,started+MAX_REQUEST_SECONDS): raise LifecycleBlocked("account_private_files_remain")
            for resource in resources:
                if resource["kind"]=="storage":
                    provider=_storage_provider(resource["identity"],claim)
                    if provider and _provider_present(client,*provider): raise LifecycleBlocked("account_provider_object_remains")
                if resource["kind"]=="report": _transition(client,claim,"verified",resource["id"])
            _remove_empty_roots(claim,resources)
            _rpc(client,"remove_account_subject167",claim)
            for resource in resources:
                if resource["kind"]!="auth":continue
                auth_id=resource["identity"]["auth_id"]
                present=_auth_present(client,auth_id)
                if present and resource["state"] in {"intent","uncertain"}:raise LifecycleBlocked("account_auth_outcome_uncertain")
                if present:
                    _transition(client,claim,"intent",resource["id"])
                    try:client.auth.admin.delete_user(auth_id)
                    except Exception:
                        if _auth_present(client,auth_id):raise LifecycleBlocked("account_auth_outcome_uncertain")
                if _auth_present(client,auth_id):raise LifecycleBlocked("account_auth_identity_remains")
                _transition(client,claim,"verified",resource["id"])
            return finish_account_fence(marker,lambda: _complete_claim(client,claim))
    except AccountWorkBusy:
        return _transition(client,claim,"retry",code="account_work_in_flight")
    except LifecycleRetry as error:
        return _transition(client,claim,"retry",code=str(error))
    except LifecycleBlocked as error:
        return _transition(client,claim,"block",code=str(error))
    except Exception as error:
        message=str(error)
        # Claim loss must NEVER transition a successor. Other unknown database
        # dependencies/policies block, leaving immutable files untouched if the
        # release transaction did not commit.
        if "account_erasure_claim_lost" in message:raise
        for code in ("shared_project_ownership","shared_learning_ownership","shared_academy_ownership","shared_commerce_ownership",
                     "account_commerce_identity_unresolved","account_commerce_provider_erasure_required",
                     "account_learning_storage_registry_mismatch","account_retention_or_adapter_required",
                     "account_dependency_release_blocked","account_inventory_adapter_required",
                     "account_inventory_limit","account_provider_object_remains"):
            if code in message:return _transition(client,claim,"block",code=code)
        raise


def run_batch(*,worker_id,client,limit=1):
    from services.provider_recovery import worker_consumption_allowed
    if not worker_consumption_allowed():return []
    capability(client)
    claims=client.rpc("claim_account_erasure167",{"p_owner":worker_id,"p_limit":limit,"p_lease_seconds":120}).execute().data
    return [process_claim(claim,client=client) for claim in claims]
