"""Durable automated BI refresh and recurring reports for candidate schema 164."""
from __future__ import annotations

import calendar
import csv
import hashlib
import json
import os
import re
import tempfile
import time as monotonic_time
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException

from data_analysis import services as data_services
from database import service_supabase
from services import bi_dashboard_service, project_dataset_service
from services.notification_service import create_tenant_notification_event
from services.upload_config import get_private_charts_dir


REPORTING_SCHEMA = 164
MAX_SCHEDULES_PER_PROJECT = 20
MAX_WIDGETS_PER_REPORT = 24
MAX_RESULT_ROWS = 500
MAX_ARTIFACT_BYTES = 1024 * 1024
MAX_REPORT_HISTORY = 100
MAX_BATCH = 20
MAX_RETRIES = 3
MAX_EXECUTION_SECONDS = 120
SAFE_CODE = re.compile(r"^[a-z0-9_.-]{1,100}$")
SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


class ReportExecutionError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool):
        super().__init__(code)
        self.code = code if SAFE_CODE.fullmatch(code) else "report_generation_failed"
        self.retryable = retryable


def _rows(response) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, dict):
        return [data]
    return [row for row in (data or []) if isinstance(row, dict)]


def _first(response) -> dict[str, Any]:
    rows = _rows(response)
    if not rows:
        raise RuntimeError("Reporting operation returned no result")
    return rows[0]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def reporting_available(*, client=None) -> bool:
    return project_dataset_service.schema_version(client=client) >= REPORTING_SCHEMA


def require_reporting_schema(*, client=None) -> None:
    if not reporting_available(client=client):
        raise HTTPException(status_code=503, detail={
            "code": "bi_reporting_upgrade_required",
            "message": "Automated reports require the database upgrade.",
        })


def validate_timezone(value: object) -> str:
    name = str(value or "").strip()
    if not name or len(name) > 64 or not re.fullmatch(r"[A-Za-z0-9_+./-]+", name):
        raise HTTPException(status_code=422, detail="Schedule timezone is invalid.")
    try:
        ZoneInfo(name)
    except ZoneInfoNotFoundError as error:
        raise HTTPException(status_code=422, detail="Schedule timezone is not an IANA timezone.") from error
    return name


def validate_local_time(value: object) -> time:
    try:
        parsed = time.fromisoformat(str(value or ""))
    except ValueError as error:
        raise HTTPException(status_code=422, detail="Schedule time must use HH:MM.") from error
    if parsed.second or parsed.microsecond or parsed.tzinfo is not None:
        raise HTTPException(status_code=422, detail="Schedule time must use whole local minutes.")
    return parsed


def _valid_local_instants(naive: datetime, zone: ZoneInfo) -> list[datetime]:
    values: list[datetime] = []
    for fold in (0, 1):
        aware = naive.replace(tzinfo=zone, fold=fold)
        utc_value = aware.astimezone(timezone.utc)
        if utc_value.astimezone(zone).replace(tzinfo=None) == naive and utc_value not in values:
            values.append(utc_value)
    return sorted(values)


def _resolve_local(naive: datetime, zone: ZoneInfo) -> datetime:
    """Repeated times choose the earlier instant; nonexistent times advance."""
    for minute in range(181):
        values = _valid_local_instants(naive + timedelta(minutes=minute), zone)
        if values:
            return values[0]
    raise ValueError("timezone_transition_unresolvable")


def next_occurrence(*, cadence: str, timezone_name: str, local_time: time,
                    weekday: int | None, month_day: int | None,
                    after: datetime) -> datetime:
    cadence = str(cadence or "").lower()
    zone = ZoneInfo(validate_timezone(timezone_name))
    if after.tzinfo is None:
        after = after.replace(tzinfo=timezone.utc)
    after = after.astimezone(timezone.utc)
    local_after = after.astimezone(zone)
    if cadence == "weekly" and (weekday is None or not 0 <= int(weekday) <= 6):
        raise HTTPException(status_code=422, detail="Weekly schedules require a weekday from 0 to 6.")
    if cadence == "monthly" and (month_day is None or not 1 <= int(month_day) <= 31):
        raise HTTPException(status_code=422, detail="Monthly schedules require a day from 1 to 31.")
    if cadence not in {"daily", "weekly", "monthly"}:
        raise HTTPException(status_code=422, detail="Report cadence is unsupported.")

    candidates: list[date] = []
    if cadence == "daily":
        candidates = [local_after.date() + timedelta(days=offset) for offset in range(0, 370)]
    elif cadence == "weekly":
        delta = (int(weekday) - local_after.weekday()) % 7
        start = local_after.date() + timedelta(days=delta)
        candidates = [start + timedelta(days=7 * offset) for offset in range(0, 54)]
    else:
        year, month = local_after.year, local_after.month
        for offset in range(0, 25):
            candidate_month = month + offset
            candidate_year = year + (candidate_month - 1) // 12
            candidate_month = (candidate_month - 1) % 12 + 1
            day = min(int(month_day), calendar.monthrange(candidate_year, candidate_month)[1])
            candidates.append(date(candidate_year, candidate_month, day))

    for candidate_date in candidates:
        naive = datetime.combine(candidate_date, local_time)
        candidate = _resolve_local(naive, zone)
        if candidate > after:
            return candidate
    raise HTTPException(status_code=422, detail="The next report occurrence could not be determined.")


def _schedule_params(*, dashboard_id: str, name: str, cadence: str, timezone_name: str,
                     local_time_value: str, weekday: int | None, month_day: int | None,
                     enabled: bool, require_ready_checkpoints: bool,
                     after: datetime | None = None) -> dict[str, Any]:
    clean_name = str(name or "").strip()
    if not 1 <= len(clean_name) <= 120:
        raise HTTPException(status_code=422, detail="Schedule name must be between 1 and 120 characters.")
    cadence = str(cadence or "").strip().lower()
    zone = validate_timezone(timezone_name)
    local_value = validate_local_time(local_time_value)
    if cadence != "weekly":
        weekday = None
    if cadence != "monthly":
        month_day = None
    next_run = next_occurrence(
        cadence=cadence, timezone_name=zone, local_time=local_value,
        weekday=weekday, month_day=month_day, after=after or _now(),
    )
    return {
        "p_dashboard_id": project_dataset_service._safe_uuid(dashboard_id, detail="Dashboard was not found."),
        "p_name": clean_name, "p_cadence": cadence, "p_timezone": zone,
        "p_local_time": local_value.isoformat(timespec="minutes"), "p_weekday": weekday,
        "p_month_day": month_day, "p_enabled": bool(enabled),
        "p_require_ready_checkpoints": bool(require_ready_checkpoints),
        "p_next_run_at": next_run.isoformat(),
    }


def list_schedules(*, tenant_id: int, project_id: str, user_id: int, client=None) -> dict:
    database = client or service_supabase
    require_reporting_schema(client=database)
    project_dataset_service.require_data_project(project_id, tenant_id=tenant_id, client=database)
    rows = _rows(database.table("bi_report_schedules").select("*")
        .eq("tenant_id", tenant_id).eq("project_id", project_dataset_service._safe_uuid(project_id))
        .eq("creator_user_id", user_id).order("created_at").limit(MAX_SCHEDULES_PER_PROJECT).execute())
    return {"items": rows}


def create_schedule(*, tenant_id: int, project_id: str, user_id: int, client=None, **values) -> dict:
    database = client or service_supabase
    require_reporting_schema(client=database)
    params = _schedule_params(**values)
    params.update(p_tenant_id=tenant_id, p_project_id=project_dataset_service._safe_uuid(project_id),
                  p_creator_user_id=user_id)
    return _first(database.rpc("create_bi_report_schedule164", params).execute())


def update_schedule(*, tenant_id: int, project_id: str, user_id: int, schedule_id: str,
                    expected_revision: int, client=None, **values) -> dict:
    database = client or service_supabase
    require_reporting_schema(client=database)
    params = _schedule_params(**values)
    params.update(p_tenant_id=tenant_id, p_project_id=project_dataset_service._safe_uuid(project_id),
                  p_creator_user_id=user_id,
                  p_schedule_id=project_dataset_service._safe_uuid(schedule_id, detail="Schedule was not found."),
                  p_expected_revision=int(expected_revision))
    try:
        return _first(database.rpc("update_bi_report_schedule164", params).execute())
    except Exception as error:
        if "revision_conflict" in str(error).lower() or "40001" in str(error):
            raise HTTPException(status_code=409, detail="The schedule changed in another session.") from error
        raise


def delete_schedule(*, tenant_id: int, project_id: str, user_id: int, schedule_id: str,
                    expected_revision: int, client=None) -> bool:
    database = client or service_supabase
    require_reporting_schema(client=database)
    response = database.rpc("delete_bi_report_schedule164", {
        "p_tenant_id": tenant_id, "p_project_id": project_dataset_service._safe_uuid(project_id),
        "p_creator_user_id": user_id,
        "p_schedule_id": project_dataset_service._safe_uuid(schedule_id, detail="Schedule was not found."),
        "p_expected_revision": int(expected_revision),
    }).execute()
    return bool(getattr(response, "data", None))


def configure_auto_refresh(*, tenant_id: int, project_id: str, user_id: int,
                           dashboard_id: str, expected_revision: int, enabled: bool,
                           client=None) -> dict:
    database = client or service_supabase
    require_reporting_schema(client=database)
    return _first(database.rpc("configure_bi_dashboard_refresh164", {
        "p_tenant_id": tenant_id, "p_project_id": project_dataset_service._safe_uuid(project_id),
        "p_creator_user_id": user_id,
        "p_dashboard_id": project_dataset_service._safe_uuid(dashboard_id, detail="Dashboard was not found."),
        "p_expected_revision": int(expected_revision), "p_enabled": bool(enabled),
    }).execute())


def _dedupe(*parts: object) -> str:
    return hashlib.sha256("\x1f".join(str(part or "") for part in parts).encode()).hexdigest()


def enqueue_report(*, tenant_id: int, project_id: str, user_id: int, dashboard_id: str,
                   trigger_type: str, due_slot: datetime | None = None,
                   schedule_id: str | None = None, idempotency_key: str | None = None,
                   client=None) -> dict:
    database = client or service_supabase
    require_reporting_schema(client=database)
    dashboard = bi_dashboard_service.get_dashboard(
        tenant_id=tenant_id, project_id=project_id, user_id=user_id,
        dashboard_id=dashboard_id, client=database,
    )
    if len(dashboard.get("widgets") or []) > MAX_WIDGETS_PER_REPORT:
        raise HTTPException(status_code=422, detail="The dashboard has too many widgets for one report.")
    slot = due_slot.astimezone(timezone.utc) if due_slot else None
    identity = idempotency_key or _dedupe(trigger_type, schedule_id, dashboard_id,
                                           dashboard["revision"], slot.isoformat() if slot else uuid4())
    return _first(database.rpc("enqueue_bi_report_run164", {
        "p_tenant_id": tenant_id, "p_project_id": project_dataset_service._safe_uuid(project_id),
        "p_creator_user_id": user_id,
        "p_dashboard_id": project_dataset_service._safe_uuid(dashboard_id, detail="Dashboard was not found."),
        "p_schedule_id": project_dataset_service._safe_uuid(schedule_id) if schedule_id else None,
        "p_trigger_type": trigger_type, "p_due_slot": slot.isoformat() if slot else None,
        "p_deduplication_key": identity,
    }).execute())


def dispatch_due_schedules(*, now: datetime | None = None, limit: int = 20, client=None) -> dict:
    database = client or service_supabase
    require_reporting_schema(client=database)
    current = (now or _now()).astimezone(timezone.utc)
    rows = _rows(database.table("bi_report_schedules").select("*").eq("enabled", True)
        .lte("next_run_at", current.isoformat()).order("next_run_at").limit(max(1, min(limit, MAX_BATCH))).execute())
    results = []
    for schedule in rows:
        due = datetime.fromisoformat(str(schedule["next_run_at"]).replace("Z", "+00:00"))
        following = next_occurrence(
            cadence=schedule["cadence"], timezone_name=schedule["timezone"],
            local_time=validate_local_time(schedule["local_time"]), weekday=schedule.get("weekday"),
            month_day=schedule.get("month_day"), after=due,
        )
        run = enqueue_report(
            tenant_id=int(schedule["tenant_id"]), project_id=schedule["project_id"],
            user_id=int(schedule["creator_user_id"]), dashboard_id=schedule["dashboard_id"],
            schedule_id=schedule["id"], trigger_type="scheduled", due_slot=due,
            idempotency_key=_dedupe("scheduled", schedule["id"], due.isoformat(), schedule["revision"]),
            client=database,
        )
        advanced = bool(getattr(database.rpc("advance_bi_report_schedule164", {
            "p_schedule_id": schedule["id"], "p_expected_revision": schedule["revision"],
            "p_due_slot": due.isoformat(), "p_next_run_at": following.isoformat(),
        }).execute(), "data", None))
        results.append({"schedule_id": schedule["id"], "run_id": run["id"], "advanced": advanced})
    return {"dispatched": len(results), "items": results}


def dispatch_data_refreshes(*, limit: int = 20, client=None) -> dict:
    database = client or service_supabase
    require_reporting_schema(client=database)
    dashboards = _rows(database.table("bi_dashboards").select("id,tenant_id,project_id,creator_user_id,revision")
        .eq("auto_refresh_enabled", True).order("updated_at").limit(max(1, min(limit, MAX_BATCH))).execute())
    created = []
    for dashboard in dashboards:
        detail = bi_dashboard_service.get_dashboard(
            tenant_id=int(dashboard["tenant_id"]), project_id=dashboard["project_id"],
            user_id=int(dashboard["creator_user_id"]), dashboard_id=dashboard["id"], client=database,
        )
        changes = []
        for widget in detail.get("widgets") or []:
            if widget["version_policy"] != "latest_committed":
                continue
            versions = project_dataset_service.list_project_dataset_versions(
                tenant_id=int(dashboard["tenant_id"]), project_id=dashboard["project_id"],
                user_id=int(dashboard["creator_user_id"]), dataset_id=widget["dataset_id"],
                limit=1, offset=0, client=database,
            )["items"]
            if versions and versions[0]["id"] != widget["dataset_version_id"]:
                changes.append((widget["id"], versions[0]["id"]))
        if changes:
            identity = _dedupe("data_refresh", dashboard["id"], dashboard["revision"],
                               json.dumps(changes, sort_keys=True))
            run = enqueue_report(
                tenant_id=int(dashboard["tenant_id"]), project_id=dashboard["project_id"],
                user_id=int(dashboard["creator_user_id"]), dashboard_id=dashboard["id"],
                trigger_type="data_refresh", idempotency_key=identity, client=database,
            )
            created.append(run["id"])
    return {"dispatched": len(created), "run_ids": created}


def list_reports(*, tenant_id: int, project_id: str, user_id: int, limit: int = 50,
                 offset: int = 0, client=None) -> dict:
    database = client or service_supabase
    require_reporting_schema(client=database)
    project_dataset_service.require_data_project(project_id, tenant_id=tenant_id, client=database)
    safe_limit = max(1, min(limit, MAX_REPORT_HISTORY))
    rows = _rows(database.table("bi_report_runs")
        .select("id,dashboard_id,schedule_id,dashboard_revision,trigger_type,due_slot,status,version_vector,warnings,error_code,artifact_filename,artifact_size_bytes,created_at,started_at,completed_at,attempts,max_attempts")
        .eq("tenant_id", tenant_id).eq("project_id", project_dataset_service._safe_uuid(project_id))
        .eq("creator_user_id", user_id).is_("archived_at", "null").order("created_at", desc=True)
        .range(offset, offset + safe_limit).execute())
    return {"items": rows[:safe_limit], "pagination": {"limit": safe_limit, "offset": offset,
                                                         "has_more": len(rows) > safe_limit}}


def get_report(*, tenant_id: int, project_id: str, user_id: int, report_id: str,
               client=None, include_storage: bool = False) -> dict:
    database = client or service_supabase
    require_reporting_schema(client=database)
    fields = "*" if include_storage else "id,dashboard_id,schedule_id,dashboard_revision,trigger_type,due_slot,status,definition_snapshot,version_vector,result_snapshot,warnings,error_code,artifact_filename,artifact_size_bytes,artifact_sha256,created_at,started_at,completed_at,attempts,max_attempts"
    rows = _rows(database.table("bi_report_runs").select(fields)
        .eq("id", project_dataset_service._safe_uuid(report_id, detail="Report was not found."))
        .eq("tenant_id", tenant_id).eq("project_id", project_dataset_service._safe_uuid(project_id))
        .eq("creator_user_id", user_id).is_("archived_at", "null").limit(1).execute())
    if not rows:
        raise HTTPException(status_code=404, detail="Report was not found.")
    return rows[0]


def archive_report(*, tenant_id: int, project_id: str, user_id: int, report_id: str,
                   client=None) -> None:
    database = client or service_supabase
    require_reporting_schema(client=database)
    project_dataset_service.require_data_project(project_id, tenant_id=tenant_id, client=database)
    archived = database.rpc("archive_bi_report_run164", {
        "p_tenant_id": tenant_id,
        "p_project_id": project_dataset_service._safe_uuid(project_id),
        "p_creator_user_id": user_id,
        "p_run_id": project_dataset_service._safe_uuid(report_id, detail="Report was not found."),
    }).execute().data
    if archived is not True:
        raise HTTPException(status_code=409, detail="Only a finished report can be archived.")


def report_artifact(*, tenant_id: int, project_id: str, user_id: int, report_id: str,
                    client=None) -> tuple[Path, str]:
    report = get_report(tenant_id=tenant_id, project_id=project_id, user_id=user_id,
                        report_id=report_id, client=client, include_storage=True)
    if report.get("status") != "completed" or not report.get("artifact_storage_key"):
        raise HTTPException(status_code=409, detail="The report export is not ready.")
    root = get_private_charts_dir().resolve()
    path = (root / str(report["artifact_storage_key"])).resolve()
    if root not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="Report export was not found.")
    if path.stat().st_size != int(report["artifact_size_bytes"]):
        raise HTTPException(status_code=409, detail="Report export integrity check failed.")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != report["artifact_sha256"]:
        raise HTTPException(status_code=409, detail="Report export integrity check failed.")
    return path, report["artifact_filename"]


def claim_runs(*, worker_id: str, limit: int = 5, lease_seconds: int = 300,
               client=None) -> list[dict[str, Any]]:
    database = client or service_supabase
    database.rpc("recover_expired_bi_report_runs164", {"p_now": _now().isoformat(), "p_limit": 100}).execute()
    return _rows(database.rpc("claim_bi_report_runs164", {
        "p_worker_id": str(worker_id)[:160], "p_limit": max(1, min(limit, MAX_BATCH)),
        "p_lease_seconds": max(30, min(lease_seconds, 1800)), "p_now": _now().isoformat(),
    }).execute())


def _safe_csv_cell(value: object) -> str:
    if value is None:
        return ""
    text = str(value).replace("\x00", "")[:4096]
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        text = "'" + text
    return text


def _report_rows(results: list[dict[str, Any]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for item in results:
        provenance = item.get("provenance") or {}
        result = item.get("result") or {}
        base = {
            "widget": _safe_csv_cell(item.get("title")),
            "status": _safe_csv_cell(item.get("status")),
            "dataset_id": _safe_csv_cell(provenance.get("dataset_id")),
            "dataset_version_id": _safe_csv_cell(provenance.get("dataset_version_id")),
            "content_hash": _safe_csv_cell(provenance.get("content_hash")),
            "operation": _safe_csv_cell(provenance.get("operation")),
        }
        kpis = result.get("kpis") if isinstance(result, dict) else None
        if isinstance(kpis, list) and kpis:
            for kpi in kpis[:MAX_RESULT_ROWS - len(output)]:
                output.append({**base, "label": _safe_csv_cell(kpi.get("label")),
                               "value": _safe_csv_cell(kpi.get("display_value", kpi.get("value")))})
        else:
            output.append({**base, "label": _safe_csv_cell(item.get("reason")), "value": ""})
        if len(output) >= MAX_RESULT_ROWS:
            break
    return output


def _write_csv_artifact(*, run: dict[str, Any], results: list[dict[str, Any]]) -> dict[str, Any]:
    rows = _report_rows(results)
    root = get_private_charts_dir().resolve()
    temporary_root = root / ".report-tmp"
    temporary_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8-sig", newline="", dir=temporary_root,
                                     prefix="report-", suffix=".csv", delete=False) as output:
        writer = csv.DictWriter(output, fieldnames=["widget", "status", "dataset_id", "dataset_version_id",
                                                      "content_hash", "operation", "label", "value"])
        writer.writeheader();writer.writerows(rows)
        temporary = Path(output.name)
    try:
        size = temporary.stat().st_size
        if size <= 0 or size > MAX_ARTIFACT_BYTES:
            raise ReportExecutionError("report_artifact_limit_exceeded", retryable=False)
        digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
        relative = Path("reports") / f"tenant_{int(run['tenant_id'])}" / str(run["id"]) / f"{digest}.csv"
        destination = (root / relative).resolve()
        if root not in destination.parents:
            raise ReportExecutionError("report_artifact_path_invalid", retryable=False)
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.replace(temporary, destination)
        title = str((run.get("definition_snapshot") or {}).get("dashboard", {}).get("name") or "report")
        safe_title = SAFE_FILENAME.sub("-", title).strip("-.")[:80] or "report"
        return {"storage_key": relative.as_posix(), "filename": f"{safe_title}-{str(run['id'])[:8]}.csv",
                "content_type": "text/csv", "size_bytes": size, "sha256": digest}
    finally:
        temporary.unlink(missing_ok=True)


def execute_run(run: dict[str, Any], *, client=None) -> tuple[str, dict[str, Any], list[dict], dict | None]:
    database = client or service_supabase
    definition = run.get("definition_snapshot") or {}
    widgets = definition.get("widgets") or []
    vector = {item.get("widget_id"): item for item in (run.get("version_vector") or [])}
    if not widgets:
        return "needs_attention", {"title": definition.get("dashboard", {}).get("name"), "widgets": []}, \
            [{"code": "report_has_no_widgets"}], None
    if len(widgets) > MAX_WIDGETS_PER_REPORT:
        raise ReportExecutionError("report_widget_limit_exceeded", retryable=False)
    results: list[dict[str, Any]] = []
    warnings: list[dict[str, str]] = []
    freshness_notes: dict[str, dict[str, Any]] = {}
    require_ready = bool((definition.get("report_policy") or {}).get("require_ready_checkpoints"))
    deadline = monotonic_time.monotonic() + MAX_EXECUTION_SECONDS
    for widget in widgets:
        if monotonic_time.monotonic() >= deadline:
            raise ReportExecutionError("report_execution_deadline_exceeded", retryable=True)
        selected = vector.get(widget.get("id"))
        if not selected:
            results.append({"widget_id": widget.get("id"), "title": widget.get("title"),
                            "status": "needs_attention", "reason": "dataset_version_unavailable"})
            warnings.append({"code": "dataset_version_unavailable", "widget_id": str(widget.get("id"))})
            continue
        try:
            dataset_id = selected["dataset_id"]
            if dataset_id not in freshness_notes:
                freshness = project_dataset_service.get_project_dataset_freshness(
                    tenant_id=int(run["tenant_id"]), project_id=run["project_id"],
                    user_id=int(run["creator_user_id"]), dataset_id=dataset_id, client=database,
                )
                resource = freshness.get("resource") or {}
                checkpoint = freshness.get("checkpoint") or {}
                committed_revision = resource.get("committed_revision")
                checkpoint_revision = checkpoint.get("target_revision")
                ready = not resource or (
                    checkpoint.get("status") == "completed"
                    and checkpoint_revision is not None
                    and committed_revision is not None
                    and int(checkpoint_revision) >= int(committed_revision)
                    and not resource.get("pending_reconciliation")
                )
                freshness_notes[dataset_id] = {
                    "available": freshness.get("available", False),
                    "checkpoint_status": checkpoint.get("status"),
                    "checkpoint_revision": checkpoint_revision,
                    "committed_revision": committed_revision,
                    "pending_reconciliation": bool(resource.get("pending_reconciliation")),
                    "ready": ready,
                }
            if require_ready and not freshness_notes[dataset_id]["ready"]:
                raise ReportExecutionError("report_checkpoint_not_ready", retryable=True)
            persistent = project_dataset_service.resolve_project_dataset_version(
                tenant_id=int(run["tenant_id"]), project_id=run["project_id"],
                user_id=int(run["creator_user_id"]), dataset_id=selected["dataset_id"],
                version_id=selected["dataset_version_id"], client=database,
            )
            analysis_spec = bi_dashboard_service.validate_analysis_spec(widget.get("analysis_spec"))
            analysis = data_services.run_assisted_analysis(
                input_path=persistent["storage_identifier"], cleaning_actions=[], question=None,
                metric=analysis_spec, language="en", symbols={}, tenant_id=str(run["tenant_id"]),
                user_id=str(run["creator_user_id"]),
            )
            results.append({"widget_id": widget["id"], "title": widget["title"], "status": "ready",
                            "result": analysis.get("result", analysis), "provenance": {
                                **selected, "project_id": run["project_id"],
                                "operation": analysis_spec["operation"],
                            }})
        except HTTPException as error:
            results.append({"widget_id": widget.get("id"), "title": widget.get("title"),
                            "status": "needs_attention", "reason": "dataset_access_revoked"})
            warnings.append({"code": "dataset_access_revoked", "widget_id": str(widget.get("id"))})
        except (KeyError, TypeError, ValueError):
            results.append({"widget_id": widget.get("id"), "title": widget.get("title"),
                            "status": "needs_attention", "reason": "schema_incompatible"})
            warnings.append({"code": "schema_incompatible", "widget_id": str(widget.get("id"))})
    ready = [item for item in results if item["status"] == "ready"]
    status = "completed" if ready else "needs_attention"
    snapshot = {"title": definition.get("dashboard", {}).get("name"),
                "generated_at": _now().isoformat(), "generic_analytics_disclosure": True,
                "widgets": results, "version_vector": list(vector.values()),
                "freshness": freshness_notes}
    artifact = _write_csv_artifact(run=run, results=results) if ready else None
    return status, snapshot, warnings, artifact


def process_claimed_run(run: dict[str, Any], *, client=None) -> dict[str, Any]:
    database = client or service_supabase
    now = _now()
    try:
        status, snapshot, warnings, artifact = execute_run(run, client=database)
        params = {
            "p_run_id": run["id"], "p_lease_token": run["lease_token"],
            "p_lease_fence": run["lease_fence"], "p_status": status,
            "p_result_snapshot": snapshot, "p_warnings": warnings,
            "p_artifact_storage_key": artifact["storage_key"] if artifact else None,
            "p_artifact_filename": artifact["filename"] if artifact else None,
            "p_artifact_content_type": artifact["content_type"] if artifact else None,
            "p_artifact_size_bytes": artifact["size_bytes"] if artifact else None,
            "p_artifact_sha256": artifact["sha256"] if artifact else None,
            "p_now": now.isoformat(),
        }
        completed = bool(getattr(database.rpc("complete_bi_report_run164", params).execute(), "data", None))
        if not completed:
            if artifact:
                (get_private_charts_dir() / artifact["storage_key"]).unlink(missing_ok=True)
            return {"id": run["id"], "status": "stale"}
        try:
            create_tenant_notification_event(
                tenant_id=run["tenant_id"], event_type="bi_report_ready" if status == "completed" else "bi_report_attention",
                source_type="bi_report", source_id=run["id"], title="Business report ready" if status == "completed" else "Business report needs attention",
                body="A scheduled analytical report is available." if status == "completed" else "A report could not calculate every widget.",
                data={"project_id": run["project_id"], "report_id": run["id"]},
            )
        except Exception:
            # Report durability must not depend on optional notification delivery.
            pass
        return {"id": run["id"], "status": status}
    except ReportExecutionError as error:
        next_state = getattr(database.rpc("fail_bi_report_run164", {
            "p_run_id": run["id"], "p_lease_token": run["lease_token"], "p_lease_fence": run["lease_fence"],
            "p_error_code": error.code, "p_retryable": error.retryable,
            "p_available_at": (now + timedelta(seconds=60 * max(1, int(run.get("attempts") or 1)))).isoformat(),
            "p_now": now.isoformat(),
        }).execute(), "data", "stale")
        return {"id": run["id"], "status": next_state, "error_code": error.code}
    except Exception as error:
        next_state = getattr(database.rpc("fail_bi_report_run164", {
            "p_run_id": run["id"], "p_lease_token": run["lease_token"], "p_lease_fence": run["lease_fence"],
            "p_error_code": "report_generation_failed", "p_retryable": True,
            "p_available_at": (now + timedelta(seconds=60 * max(1, int(run.get("attempts") or 1)))).isoformat(),
            "p_now": now.isoformat(),
        }).execute(), "data", "stale")
        result = {"id": run["id"], "status": next_state, "error_code": "report_generation_failed",
                  "exception_type": type(error).__name__}
        if os.getenv("APP_ENV", "").lower() == "test":
            result["test_diagnostic"] = str(error)[:300]
        return result


def run_worker_batch(*, worker_id: str, limit: int = 5, lease_seconds: int = 300,
                     client=None) -> dict:
    runs = claim_runs(worker_id=worker_id, limit=limit, lease_seconds=lease_seconds, client=client)
    return {"claimed": len(runs), "results": [process_claimed_run(run, client=client) for run in runs]}


def retry_report(*, tenant_id: int, project_id: str, user_id: int, report_id: str,
                 client=None) -> dict:
    database = client or service_supabase
    report = get_report(tenant_id=tenant_id, project_id=project_id, user_id=user_id,
                        report_id=report_id, client=database, include_storage=True)
    if report["status"] not in {"failed", "needs_attention"}:
        raise HTTPException(status_code=409, detail="This report is not eligible for retry.")
    if not report.get("dashboard_id"):
        raise HTTPException(status_code=409, detail="The source dashboard was deleted; this report cannot be retried.")
    return enqueue_report(
        tenant_id=tenant_id, project_id=project_id, user_id=user_id,
        dashboard_id=report["dashboard_id"], trigger_type="manual",
        idempotency_key=_dedupe("retry", report["id"], report["attempts"]), client=database,
    )
