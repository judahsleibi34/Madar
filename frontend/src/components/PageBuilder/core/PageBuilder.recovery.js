import {
  getPersistableProject,
  hashPersistableProject,
} from "./PageBuilder.editorState";

export const BUILDER_RECOVERY_FORMAT_VERSION = 1;
export const BUILDER_RECOVERY_KEY_PREFIX = "madar_app_builder_frontend_v5";
export const BUILDER_RECOVERY_MAX_AGE_MS = 30 * 24 * 60 * 60 * 1000;
export const LEGACY_BUILDER_STORAGE_KEY = "madar_app_builder_frontend_v4";

export const hashBuilderRecoverySchema = (schema = {}) => hashPersistableProject(schema);

const normalizedIdentityPart = (value) => encodeURIComponent(String(value ?? "").trim());

export const getBuilderRecoveryStorageKey = ({ userId, tenantId, projectId } = {}) => {
  const user = normalizedIdentityPart(userId);
  const tenant = normalizedIdentityPart(tenantId);
  const project = normalizedIdentityPart(projectId);
  if (!user || !tenant || !project) return "";
  return `${BUILDER_RECOVERY_KEY_PREFIX}:user:${user}:tenant:${tenant}:project:${project}`;
};

export const getLegacyBuilderStorageKey = (userId) => {
  const normalizedUserId = String(userId ?? "").trim();
  return normalizedUserId
    ? `${LEGACY_BUILDER_STORAGE_KEY}:user:${normalizedUserId}`
    : `${LEGACY_BUILDER_STORAGE_KEY}:anonymous`;
};

export const createBuilderRecoveryEnvelope = ({
  userId,
  tenantId,
  projectId,
  baseDraftRevision,
  baseSchemaHash,
  schema,
  savedAt = new Date().toISOString(),
} = {}) => ({
  version: BUILDER_RECOVERY_FORMAT_VERSION,
  user_id: String(userId ?? "").trim(),
  tenant_id: String(tenantId ?? "").trim(),
  project_id: String(projectId ?? "").trim(),
  base_draft_revision: Math.max(0, Number(baseDraftRevision) || 0),
  base_schema_hash: String(baseSchemaHash || "").trim(),
  saved_at: savedAt,
  schema: getPersistableProject(schema),
});

const isObject = (value) => Boolean(value && typeof value === "object" && !Array.isArray(value));

export const parseBuilderRecoveryEnvelope = (
  raw,
  { userId, tenantId, projectId, now = Date.now(), maxAgeMs = BUILDER_RECOVERY_MAX_AGE_MS } = {}
) => {
  if (!raw) return { status: "missing", envelope: null };

  let envelope;
  try {
    envelope = JSON.parse(raw);
  } catch {
    return { status: "malformed", envelope: null };
  }

  if (
    !isObject(envelope) ||
    envelope.version !== BUILDER_RECOVERY_FORMAT_VERSION ||
    !isObject(envelope.schema)
  ) {
    return { status: "malformed", envelope: null };
  }

  const identityMatches =
    String(envelope.user_id || "") === String(userId ?? "").trim() &&
    String(envelope.tenant_id || "") === String(tenantId ?? "").trim() &&
    String(envelope.project_id || "") === String(projectId ?? "").trim();
  if (!identityMatches) return { status: "identity_mismatch", envelope: null };

  const savedAtMs = Date.parse(envelope.saved_at);
  if (!Number.isFinite(savedAtMs)) return { status: "malformed", envelope: null };
  if (maxAgeMs >= 0 && now - savedAtMs > maxAgeMs) {
    return { status: "expired", envelope };
  }

  const baseRevision = Number(envelope.base_draft_revision);
  if (!Number.isInteger(baseRevision) || baseRevision < 0) {
    return { status: "malformed", envelope: null };
  }

  try {
    return {
      status: "valid",
      envelope: {
        ...envelope,
        base_draft_revision: baseRevision,
        // JSON.parse already produced an isolated value. Recovery is evidence,
        // not a migration input, so return its schema byte-semantically intact.
        schema: envelope.schema,
      },
    };
  } catch {
    return { status: "malformed", envelope: null };
  }
};

export const classifyBuilderRecovery = (envelope, serverRevision) => {
  const baseRevision = Number(envelope?.base_draft_revision);
  const revision = Math.max(0, Number(serverRevision) || 0);
  if (!Number.isInteger(baseRevision) || baseRevision < 0) return "invalid";
  if (baseRevision === revision) return "restorable";
  if (baseRevision < revision) return "stale_conflict";
  return "invalid";
};

export const resolveBackendFirstBuilderHydration = ({
  serverSchema,
  serverRevision,
  recoveryResult,
} = {}) => ({
  schema: serverSchema,
  source: "backend",
  recoveryDecision:
    recoveryResult?.status === "valid"
      ? classifyBuilderRecovery(recoveryResult.envelope, serverRevision)
      : null,
});

export const readBuilderRecovery = (context, storage = window.localStorage) => {
  const storageKey = getBuilderRecoveryStorageKey(context);
  if (!storageKey) return { status: "identity_incomplete", envelope: null, storageKey: "" };
  try {
    return {
      ...parseBuilderRecoveryEnvelope(storage.getItem(storageKey), context),
      storageKey,
    };
  } catch {
    return { status: "unavailable", envelope: null, storageKey };
  }
};

export const writeBuilderRecovery = (context, schema, storage = window.localStorage) => {
  const storageKey = getBuilderRecoveryStorageKey(context);
  if (!storageKey || !isObject(schema)) return false;
  const envelope = createBuilderRecoveryEnvelope({ ...context, schema });
  try {
    storage.setItem(storageKey, JSON.stringify(envelope));
    return true;
  } catch {
    return false;
  }
};

export const clearBuilderRecovery = (context, storage = window.localStorage) => {
  const storageKey = getBuilderRecoveryStorageKey(context);
  if (!storageKey) return false;
  try {
    storage.removeItem(storageKey);
    storage.removeItem(`${storageKey}:backup`);
    return true;
  } catch {
    return false;
  }
};

export const detectLegacyBuilderDraft = (userId, storage = window.localStorage) => {
  const keys = [getLegacyBuilderStorageKey(userId), LEGACY_BUILDER_STORAGE_KEY];
  try {
    const key = keys.find((candidate) => Boolean(storage.getItem(candidate)));
    return key ? { exists: true, key, raw: storage.getItem(key) } : { exists: false, key: "", raw: "" };
  } catch {
    return { exists: false, key: "", raw: "" };
  }
};
