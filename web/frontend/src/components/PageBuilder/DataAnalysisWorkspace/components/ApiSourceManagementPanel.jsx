import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Clock3, Database, FolderOpen, RefreshCw, ShieldOff } from "lucide-react";

import { apiFetch } from "../../../../utils/apiClient";
import { readApiResponse } from "../utils/api";


const INTERVALS = [900, 1800, 3600, 21600, 43200, 86400, 604800];
const newIdempotencyKey = () => (
  globalThis.crypto?.randomUUID?.() || `api-connect-${Date.now()}-${Math.random().toString(16).slice(2)}`
);

const detailMessage = (body, fallback) => {
  const detail = body?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (detail && typeof detail.message === "string" && detail.message.trim()) return detail.message;
  return fallback;
};

const credentialState = (items) => {
  if (!Array.isArray(items) || !items.length) return "missing";
  const active = items.find((item) => item.status === "active");
  if (active) {
    const expiry = active.expires_at ? new Date(active.expires_at) : null;
    return expiry && Number.isFinite(expiry.getTime()) && expiry <= new Date() ? "expired" : "ready";
  }
  return items.some((item) => item.status === "revoked") ? "revoked" : "missing";
};

const formatTimestamp = (value, t) => {
  if (!value) return t.sourceSyncNever;
  const parsed = new Date(value);
  if (!Number.isFinite(parsed.getTime())) return t.sourceSyncUnavailable;
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(parsed);
};

export default function ApiSourceManagementPanel({ registryPath, source, capabilities = {}, onReopenDataset, t }) {
  const [overview, setOverview] = useState(null);
  const [credentials, setCredentials] = useState({ status: "loading", items: [] });
  const [schedules, setSchedules] = useState({});
  const [drafts, setDrafts] = useState({});
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState("");
  const [credentialSecret, setCredentialSecret] = useState("");
  const [credentialSaveState, setCredentialSaveState] = useState("idle");
  const [credentialNotice, setCredentialNotice] = useState("");
  const [connectionState, setConnectionState] = useState("idle");
  const [connectionNotice, setConnectionNotice] = useState("");

  const sourcePath = `${registryPath}/${encodeURIComponent(source.id)}`;

  const load = useCallback(async () => {
    setStatus("loading");
    setError("");
    setSchedules({});
    try {
      const [resourceResponse, credentialResponse] = await Promise.all([
        apiFetch(`${sourcePath}/resources?limit=100`, { credentials: "include" }),
        apiFetch(`${sourcePath}/credentials`, { credentials: "include" }),
      ]);
      const [resourceBody, credentialBody] = await Promise.all([
        readApiResponse(resourceResponse), readApiResponse(credentialResponse),
      ]);
      if (!resourceResponse.ok) {
        throw new Error(detailMessage(resourceBody, t.sourceSyncLoadFailed));
      }
      setOverview(resourceBody);
      if (credentialResponse.ok) {
        setCredentials({ status: "ready", items: Array.isArray(credentialBody.items) ? credentialBody.items : [] });
      } else if (credentialResponse.status === 503) {
        setCredentials({ status: "unavailable", items: [] });
      } else {
        throw new Error(detailMessage(credentialBody, t.sourceCredentialLoadFailed));
      }

      const resources = Array.isArray(resourceBody.items) ? resourceBody.items : [];
      if (resourceBody.available === false || !resources.length) {
        setStatus("ready");
        return;
      }
      const schedulePairs = await Promise.all(resources.map(async (resource) => {
        const response = await apiFetch(
          `${sourcePath}/resources/${encodeURIComponent(resource.id)}/schedule`,
          { credentials: "include" }
        );
        const body = await readApiResponse(response);
        if (!response.ok) {
          return [resource.id, {
            state: response.status === 503 ? "unavailable" : "error",
            statusCode: response.status,
            message: detailMessage(body, t.sourceSyncLoadFailed),
          }];
        }
        if (body.available === false) return [resource.id, { state: "unavailable", schedule: null }];
        return [resource.id, { state: "ready", schedule: body.schedule }];
      }));
      const nextSchedules = Object.fromEntries(schedulePairs);
      setSchedules(nextSchedules);
      setDrafts(Object.fromEntries(resources.map((resource) => {
        const schedule = nextSchedules[resource.id]?.schedule;
        return [resource.id, {
          enabled: Boolean(schedule?.enabled),
          interval_seconds: schedule?.interval_seconds || 3600,
        }];
      })));
      setStatus("ready");
    } catch (requestError) {
      setStatus("error");
      setError(requestError.message || t.sourceSyncLoadFailed);
    }
  }, [sourcePath, t.sourceCredentialLoadFailed, t.sourceSyncLoadFailed]);

  useEffect(() => {
    void load();
  }, [load]);

  const safeCredentialState = credentials.status === "ready"
    ? credentialState(credentials.items)
    : credentials.status;
  const credentialReady = safeCredentialState === "ready";
  const providerReady = Boolean(overview?.provider_registered);
  const activeCredential = credentials.items.find((item) => item.status === "active");

  const saveCredential = async (event) => {
    event.preventDefault();
    if (!credentialSecret || credentialSaveState === "saving") return;
    setCredentialSaveState("saving");
    setCredentialNotice("");
    try {
      const response = await apiFetch(`${sourcePath}/credentials`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ credential_type: "bearer", secret: credentialSecret }),
      });
      const body = await readApiResponse(response);
      if (!response.ok) {
        const fallback = response.status === 409
          ? t.sourceCredentialConflict
          : response.status === 503 ? t.sourceCredentialUpgrade : t.sourceCredentialSaveFailed;
        throw new Error(detailMessage(body, fallback));
      }
      setCredentialSecret("");
      setCredentialSaveState("saved");
      setCredentialNotice(t.sourceCredentialSaved);
      await load();
    } catch (requestError) {
      setCredentialSaveState("error");
      setCredentialNotice(requestError.message || t.sourceCredentialSaveFailed);
    }
  };

  const revokeCredential = async () => {
    const expectedRevision = Number(activeCredential?.source_revision);
    if (!Number.isInteger(expectedRevision) || expectedRevision < 0 || credentialSaveState === "saving") return;
    setCredentialSaveState("saving");
    setCredentialNotice("");
    try {
      const response = await apiFetch(`${sourcePath}/credentials/revoke`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expected_revision: expectedRevision }),
      });
      const body = await readApiResponse(response);
      if (!response.ok) {
        const fallback = response.status === 409 ? t.sourceCredentialConflict : t.sourceCredentialRevokeFailed;
        throw new Error(detailMessage(body, fallback));
      }
      setCredentialSaveState("revoked");
      setCredentialNotice(t.sourceCredentialRevoked);
      await load();
    } catch (requestError) {
      setCredentialSaveState("error");
      setCredentialNotice(requestError.message || t.sourceCredentialRevokeFailed);
    }
  };

  const initializeConnection = async () => {
    if (!credentialReady || !providerReady || connectionState === "saving") return;
    setConnectionState("saving");
    setConnectionNotice("");
    try {
      const resourceType = String(source.resource_type || "").trim();
      const response = await apiFetch(
        `${sourcePath}/ingestions/api?resource_type=${encodeURIComponent(resourceType)}`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Idempotency-Key": newIdempotencyKey() },
        }
      );
      const body = await readApiResponse(response);
      if (!response.ok) throw new Error(detailMessage(body, t.sourceConnectionInitializeFailed));
      setConnectionState("ready");
      setConnectionNotice(t.sourceConnectionInitialized);
      await load();
    } catch (requestError) {
      setConnectionState("error");
      setConnectionNotice(requestError.message || t.sourceConnectionInitializeFailed);
    }
  };

  const saveSchedule = async (resource) => {
    const current = schedules[resource.id] || {};
    const draft = drafts[resource.id] || { enabled: false, interval_seconds: 3600 };
    setSchedules((values) => ({ ...values, [resource.id]: { ...current, state: "saving", message: "" } }));
    try {
      const response = await apiFetch(
        `${sourcePath}/resources/${encodeURIComponent(resource.id)}/schedule`,
        {
          method: "PUT",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            enabled: Boolean(draft.enabled),
            interval_seconds: Number(draft.interval_seconds),
            expected_fence: current.schedule?.fence ?? null,
          }),
        }
      );
      const body = await readApiResponse(response);
      if (!response.ok) {
        const fallback = response.status === 409
          ? t.sourceSyncConflict
          : response.status === 503 ? t.sourceSyncUpgrade : t.sourceSyncSaveFailed;
        throw Object.assign(new Error(detailMessage(body, fallback)), { status: response.status });
      }
      setSchedules((values) => ({
        ...values,
        [resource.id]: { state: "ready", schedule: body.schedule, message: t.sourceSyncSaved },
      }));
      setDrafts((values) => ({
        ...values,
        [resource.id]: {
          enabled: Boolean(body.schedule?.enabled),
          interval_seconds: body.schedule?.interval_seconds || draft.interval_seconds,
        },
      }));
    } catch (requestError) {
      setSchedules((values) => ({
        ...values,
        [resource.id]: {
          ...current,
          state: requestError.status === 503 ? "unavailable" : "error",
          message: requestError.message || t.sourceSyncSaveFailed,
        },
      }));
    }
  };

  const credentialLabel = t[`sourceCredential_${safeCredentialState}`] || t.sourceCredential_unavailable;
  const CredentialIcon = credentialReady ? CheckCircle2 : AlertTriangle;
  const resources = useMemo(() => Array.isArray(overview?.items) ? overview.items : [], [overview]);

  return (
    <div className="daw-api-source-management">
      <section className="daw-api-source-summary" aria-labelledby="daw-api-source-summary-title">
        <div>
          <span>{t.sourceConnectionKicker}</span>
          <h5 id="daw-api-source-summary-title">{t.sourceConnectionTitle}</h5>
        </div>
        <dl>
          <div><dt>{t.sourceProvider}</dt><dd>{source.provider_key || t.sourceSyncUnavailable}</dd></div>
          <div><dt>{t.sourceResourceType}</dt><dd>{source.resource_type || t.sourceSyncUnavailable}</dd></div>
          <div>
            <dt>{t.sourceCredentialStatus}</dt>
            <dd className={`is-${safeCredentialState}`}><CredentialIcon size={15} aria-hidden="true" />{credentialLabel}</dd>
          </div>
          <div><dt>{t.sourceConnectionStatus}</dt><dd>{providerReady ? t.sourceConnectionReady : t.sourceProviderUnavailable}</dd></div>
        </dl>
        {safeCredentialState !== "ready" && credentials.status !== "loading" ? (
          <p className="daw-source-sync-attention" role="status">{t.sourceCredentialAttention}</p>
        ) : null}
        {!credentialReady && providerReady && capabilities.credential_vault_available ? (
          <form className="daw-source-credential-form" onSubmit={saveCredential}>
            <label htmlFor={`daw-source-credential-${source.id}`}>
              <span>{t.sourceCredentialToken}</span>
              <input
                id={`daw-source-credential-${source.id}`}
                type="password"
                value={credentialSecret}
                minLength={1}
                maxLength={4096}
                required
                autoComplete="off"
                spellCheck="false"
                onChange={(event) => setCredentialSecret(event.target.value)}
              />
              <small>{t.sourceCredentialTokenHelp}</small>
            </label>
            <button type="submit" className="daw-primary" disabled={!credentialSecret || credentialSaveState === "saving"}>
              {credentialSaveState === "saving" ? t.working : t.sourceCredentialSave}
            </button>
          </form>
        ) : null}
        {!credentialReady && !capabilities.credential_vault_available && credentials.status !== "loading" ? (
          <p className="daw-source-registry-notice">{t.sourceCredentialUpgrade}</p>
        ) : null}
        {credentialNotice ? (
          <p className={credentialSaveState === "error" ? "daw-source-registry-error" : "daw-source-ingestion-success"} role="status">
            {credentialNotice}
          </p>
        ) : null}
        {credentialReady ? (
          <button
            type="button"
            className="daw-secondary daw-source-credential-revoke"
            disabled={credentialSaveState === "saving" || !Number.isInteger(Number(activeCredential?.source_revision))}
            onClick={revokeCredential}
          >
            <ShieldOff size={16} aria-hidden="true" />{t.sourceCredentialRevoke}
          </button>
        ) : null}
      </section>

      {status === "loading" ? <p role="status">{t.sourceSyncLoading}</p> : null}
      {status === "error" ? (
        <div className="daw-source-sync-error" role="alert">
          <p>{error}</p>
          <button type="button" className="daw-secondary" onClick={load}>
            <RefreshCw size={15} aria-hidden="true" />{t.sourceSyncRetry}
          </button>
        </div>
      ) : null}
      {status === "ready" && overview?.available === false ? (
        <p className="daw-source-registry-notice">{t.sourceResourceUpgrade}</p>
      ) : null}
      {status === "ready" && overview?.available !== false && !resources.length ? (
        <div className="daw-source-connection-setup">
          <p className="daw-source-registry-notice">{t.sourceResourceEmpty}</p>
          {credentialReady && providerReady && capabilities.incremental_resources_available ? (
            <button
              type="button"
              className="daw-primary"
              disabled={connectionState === "saving"}
              onClick={initializeConnection}
            >
              <Database size={16} aria-hidden="true" />
              {connectionState === "saving" ? t.working : t.sourceConnectionInitialize}
            </button>
          ) : null}
        </div>
      ) : null}
      {connectionNotice ? (
        <p className={connectionState === "error" ? "daw-source-registry-error" : "daw-source-ingestion-success"} role="status">
          {connectionNotice}
        </p>
      ) : null}

      {resources.map((resource) => {
        const scheduleEntry = schedules[resource.id] || { state: "loading", schedule: null };
        const schedule = scheduleEntry.schedule;
        const draft = drafts[resource.id] || { enabled: false, interval_seconds: 3600 };
        const checkpoint = resource.latest_checkpoint;
        const currentRevision = Number(resource.committed_revision || 0);
        const checkpointRevision = Number(checkpoint?.target_revision || 0);
        const checkpointCurrent = checkpoint?.status === "ready" && currentRevision > 0 && checkpointRevision === currentRevision;
        const scheduleBlocked = !providerReady || !credentialReady || scheduleEntry.state !== "ready";
        const jobStatus = schedule?.status || resource.latest_ingestion?.status || "disabled";
        return (
          <article className="daw-source-resource" key={resource.id}>
            <header>
              <Database size={18} aria-hidden="true" />
              <div><h5>{resource.resource_key}</h5><span>{t.sourceConnectedResource}</span></div>
              <span className={`daw-source-job-state is-${jobStatus}`}>
                {t[`sourceSyncStatus_${jobStatus}`] || jobStatus}
              </span>
            </header>

            <dl className="daw-source-freshness-grid">
              <div><dt>{t.sourceLastAttempt}</dt><dd>{formatTimestamp(schedule?.last_attempt_at || resource.latest_ingestion?.created_at, t)}</dd></div>
              <div><dt>{t.sourceLastSuccess}</dt><dd>{formatTimestamp(schedule?.last_success_at || resource.latest_successful_ingestion?.completed_at, t)}</dd></div>
              <div><dt>{t.sourceNextSync}</dt><dd>{draft.enabled ? formatTimestamp(schedule?.next_due_at, t) : t.sourceSyncDisabled}</dd></div>
              <div><dt>{t.sourceDatasetRevision}</dt><dd>{currentRevision || t.sourceSyncNever}</dd></div>
              <div>
                <dt>{t.sourceCheckpointStatus}</dt>
                <dd>{checkpoint ? `${t[`sourceCheckpoint_${checkpoint.status}`] || checkpoint.status} · ${t.sourceRevision} ${checkpointRevision}` : t.sourceCheckpointNone}</dd>
              </div>
              <div><dt>{t.sourceAnalyticalFreshness}</dt><dd>{checkpointCurrent ? t.sourceCheckpointCurrent : currentRevision ? t.sourceCheckpointPending : t.sourceSyncNever}</dd></div>
            </dl>

            {schedule?.last_error_category ? (
              <p className="daw-source-sync-attention" role="status">
                <AlertTriangle size={15} aria-hidden="true" />
                {t.sourceFailureCategory}: {schedule.last_error_category}
              </p>
            ) : null}
            {resource.latest_ingestion?.status === "failed" ? (
              <p className="daw-source-sync-attention" role="status">
                {t.sourceLatestIngestionFailed}: {resource.latest_ingestion.failure_code || t.sourceSyncUnavailable}
              </p>
            ) : null}
            {checkpoint?.status === "failed" ? (
              <p className="daw-source-sync-attention" role="status">
                {t.sourceCheckpointFailed}: {checkpoint.failure_code || t.sourceSyncUnavailable}
              </p>
            ) : null}

            <div className="daw-source-schedule-controls">
              <label className="daw-source-sync-toggle">
                <input
                  type="checkbox"
                  checked={Boolean(draft.enabled)}
                  disabled={scheduleBlocked || scheduleEntry.state === "saving"}
                  onChange={(event) => setDrafts((values) => ({
                    ...values,
                    [resource.id]: { ...draft, enabled: event.target.checked },
                  }))}
                />
                <span>{t.sourceAutomaticSync}</span>
              </label>
              <label>
                <span>{t.sourceSyncInterval}</span>
                <select
                  value={draft.interval_seconds}
                  disabled={scheduleBlocked || scheduleEntry.state === "saving"}
                  onChange={(event) => setDrafts((values) => ({
                    ...values,
                    [resource.id]: { ...draft, interval_seconds: Number(event.target.value) },
                  }))}
                >
                  {INTERVALS.map((seconds) => (
                    <option key={seconds} value={seconds}>{t[`sourceInterval_${seconds}`]}</option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                className="daw-primary"
                disabled={scheduleBlocked || scheduleEntry.state === "saving"}
                onClick={() => saveSchedule(resource)}
              >
                <Clock3 size={16} aria-hidden="true" />
                {scheduleEntry.state === "saving" ? t.working : t.sourceSyncSave}
              </button>
            </div>
            {resource.dataset_id && onReopenDataset ? (
              <button type="button" className="daw-secondary daw-source-open-dataset" onClick={() => onReopenDataset(resource.dataset_id)}>
                <FolderOpen size={16} aria-hidden="true" />{t.sourceIngestionOpenLatest}
              </button>
            ) : null}
            {!providerReady ? <p className="daw-source-registry-notice">{t.sourceProviderUnavailableHelp}</p> : null}
            {scheduleEntry.state === "unavailable" && !scheduleEntry.message
              ? <p className="daw-source-registry-notice">{t.sourceSyncUpgrade}</p>
              : null}
            {scheduleEntry.message ? (
              <p className={scheduleEntry.state === "ready" ? "daw-source-ingestion-success" : "daw-source-registry-error"} role="status">
                {scheduleEntry.message}
              </p>
            ) : null}
            {scheduleEntry.state === "error" ? (
              <button type="button" className="daw-secondary daw-source-sync-reload" onClick={load}>
                <RefreshCw size={15} aria-hidden="true" />{t.sourceSyncRetry}
              </button>
            ) : null}
          </article>
        );
      })}
    </div>
  );
}
