"""Private, cross-process account work fences on the shared upload filesystem.

All irreversible lifecycle work takes EX; writers take SH through completion.
Account lock inodes stay stable through work; final retirement serializes all
lock registration and follows independently verified erasure.
"""
from contextlib import contextmanager, ExitStack
import fcntl
from functools import wraps
import hashlib
import inspect
import json
import os
from pathlib import Path
import stat
import tempfile

from fastapi import HTTPException

from services.upload_config import get_data_upload_dir


class AccountWorkBusy(RuntimeError):
    pass


def _paths(tenant_id, user_id):
    tenant_id, user_id = int(tenant_id), int(user_id)
    if tenant_id <= 0 or user_id <= 0:
        raise ValueError("account_work_scope_invalid")
    root = get_data_upload_dir()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    folder = root / ".account_fences"
    try:
        folder.mkdir(mode=0o700)
    except FileExistsError:
        pass
    info = folder.lstat()
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or info.st_mode & 0o077:
        raise AccountWorkBusy("account_fence_directory_unsafe")
    name = hashlib.sha256(f"{tenant_id}:{user_id}".encode()).hexdigest()
    return folder / (name + ".lock"), folder / (name + ".hold")


@contextmanager
def _registry_lock(folder, *, exclusive):
    """Serialize opening account lock inodes with their final retirement."""
    descriptor=os.open(folder/".registry.lock",os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    try:
        info=os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_mode&0o077:
            raise AccountWorkBusy("account_fence_registry_unsafe")
        try:
            fcntl.flock(descriptor,(fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)|fcntl.LOCK_NB)
        except BlockingIOError:
            raise AccountWorkBusy("account_fence_registration_in_flight") from None
        yield
    finally:os.close(descriptor)


def _registration_allowed(tenant_id, user_id, client=None):
    """Ask candidate167 whether this account may own a new lock inode.

    The check runs while the shared registration lock is held.  Finalization
    holds the exclusive registration lock while it removes the inode and the
    database subject, so a stale process can never validate before retirement
    and create after it.
    """
    from database import service_supabase
    from services.project_dataset_service import schema_version
    database_client = client or service_supabase
    version = schema_version(client=database_client)
    if 146 <= version <= 166:
        return True
    if version != 167:
        raise AccountWorkBusy("account_fence_schema_unsupported")
    try:
        allowed = database_client.rpc("account_fence_registration167", {
            "p_tenant_id": int(tenant_id), "p_user_id": int(user_id),
        }).execute().data
    except Exception as error:
        raise AccountWorkBusy("account_fence_registration_unavailable") from error
    return allowed is True


@contextmanager
def account_lock(tenant_id, user_id, *, exclusive=False, client=None):
    lock_path, marker = _paths(tenant_id, user_id)
    descriptor=None
    try:
        with _registry_lock(lock_path.parent,exclusive=False):
            if not lock_path.exists() and not _registration_allowed(tenant_id,user_id,client):
                if not exclusive:
                    raise HTTPException(status_code=409,detail={"code":"account_unavailable","message":"Account processing is unavailable."})
                raise AccountWorkBusy("account_fence_account_absent")
            descriptor=os.open(lock_path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
            info=os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_mode&0o077:
                raise AccountWorkBusy("account_fence_file_unsafe")
            try:
                fcntl.flock(descriptor,(fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)|fcntl.LOCK_NB)
            except BlockingIOError:
                raise AccountWorkBusy("account_work_in_flight") from None
            if not exclusive and (marker.exists() or marker.is_symlink()):
                raise HTTPException(status_code=409,detail={"code":"account_processing_frozen","message":"Account processing is disabled."})
        yield marker
    finally:
        if descriptor is not None:os.close(descriptor)


def finish_account_fence(marker, finalizer):
    """Erase account coordination identifiers before the final database ACK.

    Caller owns account EX. Registry EX proves that no other process is paused
    between opening its inode and acquiring flock. New requests recheck the live
    account/session after acquiring SH; stale worker effects require live leases.
    A failed ACK restores the hold before opening registration again.
    """
    lock_path=marker.with_suffix(".lock")
    with _registry_lock(marker.parent,exclusive=True):
        if marker.is_symlink() or lock_path.is_symlink():
            raise AccountWorkBusy("account_fence_identity_unsafe")
        descriptor=os.open(marker,os.O_RDONLY|os.O_NOFOLLOW)
        try:
            info=os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>4096:
                raise AccountWorkBusy("account_fence_identity_unsafe")
            receipt=json.loads(os.read(descriptor,4096))
        finally:os.close(descriptor)
        directory=os.open(marker.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            try:
                marker.unlink();lock_path.unlink();os.fsync(directory)
                return finalizer()
            except Exception:
                if not lock_path.exists():
                    fd=os.open(lock_path,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
                    os.close(fd)
                if not marker.exists():publish_hold(marker,receipt)
                os.fsync(directory)
                raise
        finally:os.close(directory)



def publish_hold(marker: Path, receipt: dict):
    if marker.is_symlink():
        raise AccountWorkBusy("account_hold_symlink_refused")
    with tempfile.NamedTemporaryFile(dir=marker.parent, prefix=".hold-", delete=False) as output:
        temporary = Path(output.name)
        output.write(json.dumps(receipt, sort_keys=True).encode())
        output.flush();os.fsync(output.fileno())
    try:
        os.chmod(temporary, 0o600)
        os.replace(temporary, marker)
        directory = os.open(marker.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try: os.fsync(directory)
        finally: os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def scoped_work(argument, user_field, *, tenant_field="tenant_id"):
    """Wrap the entire existing job, including acknowledgement and cleanup."""
    def decorate(function):
        signature = inspect.signature(function)
        def context(args, kwargs):
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            row = bound.arguments[argument]
            client = bound.arguments.get("client") or function.__globals__.get("service_supabase")
            return account_lock(row[tenant_field], row[user_field], client=client)
        if inspect.iscoroutinefunction(function):
            @wraps(function)
            async def asynchronous(*args, **kwargs):
                with context(args, kwargs):
                    return await function(*args, **kwargs)
            return asynchronous
        @wraps(function)
        def synchronous(*args, **kwargs):
            with context(args, kwargs):
                return function(*args, **kwargs)
        return synchronous
    return decorate


def account_file_work(function):
    signature = inspect.signature(function)
    @wraps(function)
    def wrapped(*args, **kwargs):
        bound = signature.bind(*args, **kwargs)
        bound.apply_defaults()
        client = bound.arguments.get("client") or function.__globals__.get("service_supabase")
        with account_lock(bound.arguments["tenant_id"], bound.arguments["user_id"], client=client):
            return function(*args, **kwargs)
    return wrapped


def calendar_work(function):
    """Fence a claimed calendar job through provider effects and acknowledgement."""
    signature=inspect.signature(function)
    @wraps(function)
    def wrapped(job, *args, **kwargs):
        bound=signature.bind(job,*args,**kwargs);bound.apply_defaults()
        service_supabase=bound.arguments.get('client') or function.__globals__.get('service_supabase')
        if service_supabase is None:
            from database import service_supabase
        from services.project_dataset_service import schema_version
        from services.account_recovery_service import require_processing_account
        version=schema_version(client=service_supabase)
        if 146<=version<=166:return function(job,*args,**kwargs)
        if version!=167:raise HTTPException(status_code=503,detail="Account processing schema is unsupported.")
        rows=service_supabase.table("calendar_sync_connections").select("tenant_id,user_id").eq("id",job["connection_id"]).eq("tenant_id",job["tenant_id"]).limit(1).execute().data
        if not rows:raise HTTPException(status_code=409,detail="Calendar connection is unavailable.")
        identities={(int(rows[0]["tenant_id"]),int(rows[0]["user_id"]))}
        if job.get("task_id"):
            tasks=service_supabase.table("calendar_tasks").select("tenant_id,owner_user_id").eq("id",job["task_id"]).eq("tenant_id",job["tenant_id"]).limit(1).execute().data
            if not tasks:raise HTTPException(status_code=409,detail="Calendar task is unavailable.")
            identities.add((int(tasks[0]["tenant_id"]),int(tasks[0]["owner_user_id"])))
        with ExitStack() as stack:
            for tenant,user in sorted(identities):
                stack.enter_context(account_lock(tenant,user,client=service_supabase))
                require_processing_account(tenant_id=tenant,user_id=user,client=service_supabase)
            return function(job,*args,**kwargs)
    return wrapped


def _notification_resource_owner(client,event):
    kind=event.get('source_type');source=event.get('source_id');tenant=event['tenant_id']
    if kind=='bi_report':
        rows=client.table('bi_report_runs').select('tenant_id,creator_user_id').eq('id',source).eq('tenant_id',tenant).limit(1).execute().data
        column='creator_user_id'
    elif kind=='calendar_task':
        rows=client.table('calendar_tasks').select('tenant_id,owner_user_id').eq('id',source).eq('tenant_id',tenant).limit(1).execute().data
        column='owner_user_id'
    elif kind=='calendar_event':
        resources=client.table('calendar_events').select('calendar_id').eq('id',source).eq('tenant_id',tenant).limit(1).execute().data
        rows=(client.table('calendars').select('tenant_id,owner_user_id').eq('id',resources[0]['calendar_id']).eq('tenant_id',tenant).limit(1).execute().data) if resources else []
        column='owner_user_id'
    else:return None
    if not rows or rows[0].get(column) is None:
        raise HTTPException(status_code=409,detail='Notification resource is unavailable.')
    return int(rows[0]['tenant_id']),int(rows[0][column])


def notification_work(function):
    """Fence the recipient and registered BI/Calendar resource owner."""
    signature=inspect.signature(function)
    @wraps(function)
    def wrapped(*args,**kwargs):
        bound=signature.bind(*args,**kwargs);row=bound.arguments['row']
        client=bound.arguments.get('client') or function.__globals__.get('service_supabase')
        identities=set();resource_owner=None
        if row.get('user_id') is not None and row.get('tenant_id') is not None:
            identities.add((int(row['tenant_id']),int(row['user_id'])))
        event_id=row.get('event_id') or (row.get('payload') or {}).get('event_id')
        if event_id:
            events=client.table('notification_events').select('source_type,source_id,tenant_id').eq('id',event_id).limit(1).execute().data
            if not events:raise HTTPException(status_code=409,detail='Notification event is unavailable.')
            resource_owner=_notification_resource_owner(client,events[0])
            if resource_owner is not None:identities.add(resource_owner)
        # User IDs are global. A notification may target a membership in a
        # different tenant from the account's home tenant: fence both scopes.
        homes={}
        for tenant_id,user_id in sorted(identities):
            live=client.table('users').select('id,tenant_id,account_status').eq('id',user_id).limit(1).execute().data
            if not live:raise HTTPException(status_code=409,detail='Notification account is unavailable.')
            homes[user_id]=live[0].get('tenant_id')
            if homes[user_id] is not None:identities.add((int(homes[user_id]),user_id))
        with ExitStack() as stack:
            for identity in sorted(identities):stack.enter_context(account_lock(*identity,client=client))
            # A pause before opening the fence can outlive final lock retirement.
            # Revalidate accounts AND authoritative ownership after acquiring SH.
            for tenant_id,user_id in sorted(identities):
                live=client.table('users').select('id,tenant_id,account_status').eq('id',user_id).limit(1).execute().data
                if not live or live[0].get('account_status')=='deletion_pending' or live[0].get('tenant_id')!=homes[user_id]:
                    raise HTTPException(status_code=409,detail='Notification account is unavailable.')
            if event_id:
                current=client.table('notification_events').select('source_type,source_id,tenant_id').eq('id',event_id).limit(1).execute().data
                if current!=events or _notification_resource_owner(client,current[0])!=resource_owner:
                    raise HTTPException(status_code=409,detail='Notification resource is unavailable.')
            return function(*args,**kwargs)
    return wrapped


def protect_request(request, tenant_id, user_id, *, client=None):
    state = request.scope.setdefault("state", {})
    if not state.get("account_work_middleware"):
        raise RuntimeError("account_work_middleware_required")
    identity = (int(tenant_id), int(user_id))
    contexts=state.setdefault("account_work_contexts",{})
    if identity in contexts:
        return
    context = account_lock(*identity,client=client)
    context.__enter__()
    contexts[identity]=context


def release_request_scope(request, tenant_id, user_id):
    """Explicit account actions leave their read scope before taking EX.

    Enrollment reauthorizes under its database/user lock; this transition does
    not accept an action or perform file/provider work in the unlocked gap.
    """
    contexts=request.scope.get("state",{}).get("account_work_contexts",{})
    context=contexts.pop((int(tenant_id),int(user_id)),None)
    if context is not None:context.__exit__(None,None,None)


class AccountWorkFenceMiddleware:
    def __init__(self, app): self.app = app
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http": scope.setdefault("state", {})["account_work_middleware"] = True
        try:
            if scope["type"]=="http" and scope.get("method") in {"POST","PUT","PATCH"}:
                from services.request_body_limits import ASSESSMENT_RECORDING_RE, DATASET_UPLOAD_RE, UPLOAD_ROUTE_RE, _is_builder_asset_upload_path
                path=scope.get("path","")
                content_type=next((value.decode("latin-1") for key,value in scope.get("headers",[]) if key.lower()==b"content-type"),"")
                if content_type.lower().startswith("multipart/") and (DATASET_UPLOAD_RE.fullmatch(path) or UPLOAD_ROUTE_RE.fullmatch(path) or ASSESSMENT_RECORDING_RE.fullmatch(path) or _is_builder_asset_upload_path(path)):
                    from starlette.concurrency import run_in_threadpool
                    from starlette.requests import Request
                    from starlette.responses import JSONResponse
                    from database import service_supabase
                    from services.project_dataset_service import schema_version
                    from services.auth_service import get_authenticated_user_row
                    try:
                        version=await run_in_threadpool(schema_version,client=service_supabase)
                        if version==167:
                            # No refresh side effects before an interrupted body:
                            # clients refresh a stale access credential, then retry.
                            # Endpoint authorization/entitlements still run normally.
                            await run_in_threadpool(get_authenticated_user_row,Request(scope,receive),allow_refresh=False)
                        elif not 146<=version<=166:
                            raise HTTPException(status_code=503,detail="Account upload schema is unsupported.")
                    except HTTPException as error:
                        await JSONResponse({"detail":error.detail},status_code=error.status_code,headers=error.headers)(scope,receive,send)
                        return
            await self.app(scope, receive, send)
        finally:
            contexts=scope.get("state",{}).pop("account_work_contexts",{})
            for context in reversed(list(contexts.values())):context.__exit__(None,None,None)
