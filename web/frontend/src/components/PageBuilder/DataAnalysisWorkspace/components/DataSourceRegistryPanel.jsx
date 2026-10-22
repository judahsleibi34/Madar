import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertCircle, Archive, CheckCircle2, Database, FileSpreadsheet,
  FileUp, FolderOpen, PlugZap, Plus, RefreshCw,
} from "lucide-react";

import { apiFetch } from "../../../../utils/apiClient";
import { API_URL, readApiResponse } from "../utils/api";
import ApiSourceManagementPanel from "./ApiSourceManagementPanel";

const emptyCapabilities = {
  source_registry_available: false,
  api_sources_available: false,
  incremental_resources_available: false,
  credential_vault_available: false,
  automatic_sync_available: false,
  providers: [],
};

const detailValue = (body) => body?.detail;
const errorMessage = (body, fallback) => {
  const detail = detailValue(body);
  if (typeof detail === "string" && detail.trim()) return detail;
  if (detail && typeof detail.message === "string" && detail.message.trim()) return detail.message;
  return fallback;
};
const errorCode = (body) => String(detailValue(body)?.code || body?.code || "").trim();
const registryFailure = (response, body, t) => {
  const message = errorMessage(body, "");
  const code = errorCode(body);
  if (response.status === 401) return t.sourceRegistryUnauthorized;
  if (response.status === 403) return t.sourceRegistryForbidden;
  if (response.status === 404 && message === "Not Found") return t.sourceRegistryBackendMismatch;
  if (response.status === 404) return message || t.sourceRegistryProjectMissing;
  if (response.status === 409) return message || t.sourceRegistryConflict;
  if (response.status === 422) return message || t.sourceRegistryInvalid;
  if (response.status === 429) return t.sourceRegistryRateLimited;
  if (response.status === 503 || code.endsWith("upgrade_required")) return message || t.sourceRegistryUpgrade;
  return message || t.sourceRegistryLoadFailed;
};
const newIdempotencyKey = () => (
  globalThis.crypto?.randomUUID?.() || `upload-${Date.now()}-${Math.random().toString(16).slice(2)}`
);
const formatTimestamp = (value, fallback) => {
  if (!value) return fallback;
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return fallback;
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
};

export default function DataSourceRegistryPanel({ projectId, user, t, onDatasetImported, onReopenDataset }) {
  const [sources, setSources] = useState([]);
  const [capabilities, setCapabilities] = useState(emptyCapabilities);
  const [status, setStatus] = useState("loading");
  const [displayName, setDisplayName] = useState("");
  const [sourceType, setSourceType] = useState("spreadsheet_upload");
  const [providerKey, setProviderKey] = useState("");
  const [resourceType, setResourceType] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [selectedSourceId, setSelectedSourceId] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const [ingestions, setIngestions] = useState([]);
  const [ingestionStatus, setIngestionStatus] = useState("idle");
  const [ingestionNotice, setIngestionNotice] = useState("");
  const userId = user?.id;
  const dataProjectPath = userId && projectId
    ? `${API_URL}/users/${encodeURIComponent(userId)}/data/projects/${encodeURIComponent(projectId)}`
    : "";
  const registryPath = dataProjectPath ? `${dataProjectPath}/sources` : "";
  const providers = useMemo(
    () => Array.isArray(capabilities.providers) ? capabilities.providers : [],
    [capabilities.providers]
  );
  const selectedProvider = providers.find((provider) => provider.key === providerKey) || providers[0];
  const selectedResourceType = selectedProvider?.resources?.some((resource) => resource.key === resourceType)
    ? resourceType
    : (selectedProvider?.resources?.[0]?.key || "");

  const loadRegistry = useCallback(async ({ preferredSourceId = "", refreshCapabilities = true } = {}) => {
    if (!registryPath) {
      setSources([]);
      setStatus("unavailable");
      return;
    }
    setStatus("loading");
    setError("");
    try {
      const [sourceResponse, capabilityResponse] = await Promise.all([
        apiFetch(`${registryPath}?limit=100`, { credentials: "include" }),
        refreshCapabilities
          ? apiFetch(`${dataProjectPath}/source-capabilities`, { credentials: "include" })
          : Promise.resolve(null),
      ]);
      const [sourceBody, capabilityBody] = await Promise.all([
        readApiResponse(sourceResponse),
        capabilityResponse ? readApiResponse(capabilityResponse) : Promise.resolve(null),
      ]);
      if (!sourceResponse.ok) throw new Error(registryFailure(sourceResponse, sourceBody, t));
      if (capabilityResponse?.ok) {
        setCapabilities({ ...emptyCapabilities, ...capabilityBody });
        const firstProvider = capabilityBody.providers?.[0];
        setProviderKey((current) => current || firstProvider?.key || "");
        setResourceType((current) => current || firstProvider?.resources?.[0]?.key || "");
      } else if (capabilityResponse) {
        setCapabilities(emptyCapabilities);
      }
      if (sourceBody.available === false) {
        setSources([]);
        setStatus("unavailable");
        return;
      }
      const items = Array.isArray(sourceBody.items) ? sourceBody.items : [];
      setSources(items);
      setSelectedSourceId((current) => {
        const requested = preferredSourceId || current;
        return items.some((item) => item.id === requested) ? requested : (items[0]?.id || "");
      });
      setStatus("ready");
    } catch (requestError) {
      setStatus("error");
      setError(requestError.message || t.sourceRegistryLoadFailed);
    }
  }, [dataProjectPath, registryPath, t]);

  useEffect(() => {
    queueMicrotask(() => { void loadRegistry(); });
  }, [loadRegistry]);

  useEffect(() => {
    let cancelled = false;
    if (!registryPath || !selectedSourceId) {
      queueMicrotask(() => { if (!cancelled) setIngestions([]); });
      return () => { cancelled = true; };
    }
    queueMicrotask(() => { if (!cancelled) setIngestionStatus("loading"); });
    void apiFetch(`${registryPath}/${encodeURIComponent(selectedSourceId)}/ingestions?limit=20`, { credentials: "include" })
      .then(async (response) => ({ response, body: await readApiResponse(response) }))
      .then(({ response, body }) => {
        if (cancelled) return;
        if (!response.ok) throw new Error(registryFailure(response, body, t));
        if (body.available === false) {
          setIngestions([]);
          setIngestionStatus("unavailable");
          return;
        }
        setIngestions(Array.isArray(body.items) ? body.items : []);
        setIngestionStatus("ready");
      })
      .catch((requestError) => {
        if (cancelled) return;
        setIngestionStatus("error");
        setIngestionNotice(requestError.message || t.sourceIngestionLoadFailed);
      });
    return () => { cancelled = true; };
  }, [registryPath, selectedSourceId, t]);

  const trimmedName = displayName.trim();
  const apiSelectionReady = Boolean(selectedProvider && selectedResourceType);
  const canCreate = status === "ready" && !isSaving && Boolean(trimmedName)
    && (sourceType === "spreadsheet_upload" || apiSelectionReady);

  const createSource = async (event) => {
    event.preventDefault();
    if (!canCreate) return;
    setIsSaving(true);
    setError("");
    setNotice("");
    try {
      const payload = { source_type: sourceType, display_name: trimmedName };
      if (sourceType === "api_provider") {
        payload.provider_key = selectedProvider.key;
        payload.resource_type = selectedResourceType;
      }
      const response = await apiFetch(registryPath, {
        method: "POST", credentials: "include", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = await readApiResponse(response);
      if (!response.ok) throw new Error(registryFailure(response, body, t));
      setDisplayName("");
      setNotice(t.sourceRegistryCreated);
      await loadRegistry({ preferredSourceId: body.id, refreshCapabilities: false });
    } catch (requestError) {
      setError(requestError.message || t.sourceRegistryCreateFailed);
    } finally {
      setIsSaving(false);
    }
  };

  const archiveSource = async (sourceId) => {
    if (!sourceId || isSaving) return;
    setIsSaving(true);
    setError("");
    setNotice("");
    try {
      const response = await apiFetch(`${registryPath}/${encodeURIComponent(sourceId)}`, {
        method: "PATCH", credentials: "include", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "archived" }),
      });
      const body = await readApiResponse(response);
      if (!response.ok) throw new Error(registryFailure(response, body, t));
      await loadRegistry({ refreshCapabilities: false });
    } catch (requestError) {
      setError(requestError.message || t.sourceRegistryArchiveFailed);
    } finally {
      setIsSaving(false);
    }
  };

  const uploadToSource = async (event) => {
    event.preventDefault();
    if (!selectedSourceId || !selectedFile || ingestionStatus === "uploading") return;
    setIngestionStatus("uploading");
    setIngestionNotice("");
    const payload = new FormData();
    payload.append("file", selectedFile);
    try {
      const response = await apiFetch(`${registryPath}/${encodeURIComponent(selectedSourceId)}/ingestions/upload`, {
        method: "POST", credentials: "include", headers: { "Idempotency-Key": newIdempotencyKey() }, body: payload,
      });
      const body = await readApiResponse(response);
      if (!response.ok) throw new Error(registryFailure(response, body, t));
      const completed = {
        id: body.ingestion_run_id, source_id: selectedSourceId, status: "succeeded",
        result_dataset_id: body.persistent_dataset_id, result_version_id: body.dataset_version_id,
        created_at: new Date().toISOString(),
      };
      setIngestions((current) => [completed, ...current.filter((item) => item.id !== completed.id)]);
      setSources((current) => current.map((source) => source.id === selectedSourceId
        ? { ...source, latest_dataset_id: body.persistent_dataset_id, latest_version_id: body.dataset_version_id }
        : source));
      setSelectedFile(null);
      setIngestionStatus("ready");
      setIngestionNotice(t.sourceIngestionSucceeded);
      await onDatasetImported?.(body);
    } catch (requestError) {
      setIngestionStatus("error");
      setIngestionNotice(requestError.message || t.sourceIngestionFailed);
    }
  };

  const selectedSource = sources.find((source) => source.id === selectedSourceId);

  return (
    <section className="daw-card daw-section-card daw-source-registry" aria-labelledby="daw-source-registry-title">
      <div className="daw-section-heading daw-source-registry-heading">
        <span>{t.sourceRegistryKicker}</span>
        <h3 id="daw-source-registry-title">{t.sourceRegistryTitle}</h3>
        <p>{t.sourceRegistryHint}</p>
      </div>

      {status === "loading" ? (
        <div className="daw-source-loading" role="status" aria-label={t.sourceRegistryLoading}><span /><span /><span /></div>
      ) : null}
      {status === "error" ? (
        <div className="daw-source-state is-error" role="alert">
          <AlertCircle size={21} aria-hidden="true" />
          <div><strong>{t.sourceRegistryErrorTitle}</strong><p>{error}</p></div>
          <button type="button" className="daw-secondary" onClick={() => loadRegistry()}><RefreshCw size={16} aria-hidden="true" />{t.sourceSyncRetry}</button>
        </div>
      ) : null}
      {status === "unavailable" ? (
        <div className="daw-source-state" role="status">
          <Database size={21} aria-hidden="true" />
          <div><strong>{t.sourceRegistryUpgradeTitle}</strong><p>{t.sourceRegistryUpgrade}</p></div>
        </div>
      ) : null}

      {status === "ready" ? (
        <>
          <section className="daw-source-overview" aria-labelledby="daw-source-overview-title">
            <div className="daw-source-subheading">
              <div><span>{t.sourceOverviewKicker}</span><h4 id="daw-source-overview-title">{t.sourceOverviewTitle}</h4></div>
              <span className="daw-source-count">{sources.length}</span>
            </div>
            {sources.length ? (
              <div className="daw-source-registry-list">
                {sources.map((source) => {
                  const apiSource = source.source_type === "api_provider";
                  const SourceIcon = apiSource ? PlugZap : FileSpreadsheet;
                  return (
                    <article key={source.id} className={source.id === selectedSourceId ? "is-selected" : ""}>
                      <SourceIcon size={19} aria-hidden="true" />
                      <div className="daw-source-card-copy">
                        <strong>{source.display_name}</strong>
                        <span>{apiSource ? `${t.sourceRegistryApi} · ${source.provider_key || t.sourceSyncUnavailable}` : t.sourceRegistrySpreadsheet}</span>
                        <small>
                          {source.latest_dataset_id ? t.sourceDatasetReady : t.sourceDatasetWaiting}
                          {source.last_successful_sync_at ? ` · ${t.sourceLastSuccessShort} ${formatTimestamp(source.last_successful_sync_at, t.sourceSyncNever)}` : ""}
                        </small>
                      </div>
                      <button type="button" className="daw-secondary" aria-pressed={source.id === selectedSourceId} onClick={() => setSelectedSourceId(source.id)}>
                        {source.id === selectedSourceId ? t.sourceRegistrySelected : t.sourceRegistrySelect}
                      </button>
                      <button type="button" className="daw-icon-button" aria-label={`${t.sourceRegistryArchive} ${source.display_name}`} title={t.sourceRegistryArchive} disabled={isSaving} onClick={() => archiveSource(source.id)}>
                        <Archive size={17} aria-hidden="true" />
                      </button>
                    </article>
                  );
                })}
              </div>
            ) : (
              <div className="daw-source-empty"><Database size={22} aria-hidden="true" /><div><strong>{t.sourceRegistryEmptyTitle}</strong><p>{t.sourceRegistryEmpty}</p></div></div>
            )}
          </section>

          <section className="daw-source-add" aria-labelledby="daw-source-add-title">
            <div className="daw-source-subheading"><div><span>{t.sourceAddKicker}</span><h4 id="daw-source-add-title">{t.sourceAddTitle}</h4></div></div>
            <div className="daw-source-type-grid" role="group" aria-label={t.sourceTypeLabel}>
              <button type="button" className={sourceType === "spreadsheet_upload" ? "is-active" : ""} aria-pressed={sourceType === "spreadsheet_upload"} onClick={() => setSourceType("spreadsheet_upload") }>
                <FileSpreadsheet size={19} aria-hidden="true" /><span><strong>{t.sourceTypeSpreadsheet}</strong><small>{t.sourceTypeSpreadsheetHint}</small></span>
              </button>
              <button type="button" className={sourceType === "api_provider" ? "is-active" : ""} aria-pressed={sourceType === "api_provider"} disabled={!capabilities.api_sources_available || !providers.length} onClick={() => setSourceType("api_provider") }>
                <PlugZap size={19} aria-hidden="true" /><span><strong>{t.sourceTypeApi}</strong><small>{t.sourceTypeApiHint}</small></span>
              </button>
            </div>
            {!providers.length ? <p className="daw-source-registry-notice">{t.sourceNoApiProviders}</p> : null}
            <form className="daw-source-registry-form" onSubmit={createSource}>
              <label>
                <span>{t.sourceRegistryName}</span>
                <input value={displayName} maxLength={255} required aria-describedby="daw-source-name-help" placeholder={t.sourceRegistryPlaceholder} onChange={(event) => setDisplayName(event.target.value)} />
                <small id="daw-source-name-help">{t.sourceRegistryNameHelp}</small>
              </label>
              {sourceType === "api_provider" && selectedProvider ? (
                <>
                  <label><span>{t.sourceProvider}</span><select value={selectedProvider.key} onChange={(event) => { const provider = providers.find((item) => item.key === event.target.value); setProviderKey(event.target.value); setResourceType(provider?.resources?.[0]?.key || ""); }}>{providers.map((provider) => <option key={provider.key} value={provider.key}>{provider.label}</option>)}</select></label>
                  <label><span>{t.sourceResourceType}</span><select value={selectedResourceType} onChange={(event) => setResourceType(event.target.value)}>{(selectedProvider.resources || []).map((resource) => <option key={resource.key} value={resource.key}>{resource.label}</option>)}</select></label>
                </>
              ) : null}
              <button className="daw-primary" type="submit" disabled={!canCreate}><Plus size={16} aria-hidden="true" />{isSaving ? t.working : sourceType === "api_provider" ? t.sourceRegistryAddApi : t.sourceRegistryAdd}</button>
            </form>
            {error ? <p className="daw-source-registry-error" role="alert">{error}</p> : null}
            {notice ? <p className="daw-source-ingestion-success" role="status"><CheckCircle2 size={16} aria-hidden="true" />{notice}</p> : null}
          </section>

          {selectedSource ? (
            <section className="daw-source-ingestion" aria-labelledby="daw-source-ingestion-title">
              <div>
                <span>{selectedSource.source_type === "api_provider" ? t.sourceConnectionKicker : t.sourceIngestionKicker}</span>
                <h4 id="daw-source-ingestion-title">{selectedSource.display_name}</h4>
                <p>{selectedSource.source_type === "api_provider" ? t.sourceApiDetailHint : t.sourceIngestionHint}</p>
              </div>
              {selectedSource.source_type === "api_provider" ? (
                <ApiSourceManagementPanel
                  registryPath={registryPath}
                  source={selectedSource}
                  capabilities={capabilities}
                  onReopenDataset={onReopenDataset}
                  t={t}
                />
              ) : ingestionStatus === "unavailable" ? (
                <p className="daw-source-registry-notice">{t.sourceIngestionUpgrade}</p>
              ) : (
                <>
                  <form className="daw-source-ingestion-form" onSubmit={uploadToSource}>
                    <label><span>{t.sourceIngestionFile}</span><input type="file" accept=".csv,.xls,.xlsx" onChange={(event) => setSelectedFile(event.target.files?.[0] || null)} /></label>
                    <button type="submit" className="daw-primary" disabled={!selectedFile || ingestionStatus === "uploading"}><FileUp size={16} aria-hidden="true" />{ingestionStatus === "uploading" ? t.working : t.sourceIngestionUpload}</button>
                  </form>
                  {!selectedFile ? <small className="daw-source-control-help">{t.sourceChooseFileHelp}</small> : null}
                  {ingestionNotice ? <p className={ingestionStatus === "error" ? "daw-source-registry-error" : "daw-source-ingestion-success"} role="status">{ingestionNotice}</p> : null}
                  {selectedSource.latest_dataset_id && onReopenDataset ? <button type="button" className="daw-secondary daw-source-ingestion-open" onClick={() => onReopenDataset(selectedSource.latest_dataset_id)}><FolderOpen size={16} aria-hidden="true" />{t.sourceIngestionOpenLatest}</button> : null}
                  {ingestions.length ? (
                    <div className="daw-source-ingestion-history">
                      <strong>{t.sourceIngestionHistory}</strong>
                      {ingestions.map((ingestion) => <div key={ingestion.id}><span>{t[`sourceIngestionStatus_${ingestion.status}`] || ingestion.status}</span>{ingestion.result_dataset_id && onReopenDataset ? <button type="button" onClick={() => onReopenDataset(ingestion.result_dataset_id)}>{t.sourceIngestionOpen}</button> : null}</div>)}
                    </div>
                  ) : null}
                </>
              )}
            </section>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
