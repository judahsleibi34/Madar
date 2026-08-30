const STORAGE_PREFIX = "madar:runtime-form-drafts:v1:";
const STORAGE_VERSION = 1;

const getStorageKey = (siteIdentifier) =>
  `${STORAGE_PREFIX}${String(siteIdentifier || "").trim().toLowerCase()}`;

export const readRuntimeFormDrafts = (storage, siteIdentifier) => {
  if (!storage || !siteIdentifier) return {};

  try {
    const key = getStorageKey(siteIdentifier);
    const parsed = JSON.parse(storage.getItem(key) || "null");
    if (parsed?.version !== STORAGE_VERSION || !parsed.drafts || typeof parsed.drafts !== "object") {
      return {};
    }

    return parsed.drafts;
  } catch {
    return {};
  }
};

export const saveRuntimeFormDraft = (
  storage,
  siteIdentifier,
  instanceKey,
  draft,
  now = Date.now()
) => {
  if (!storage || !siteIdentifier || !instanceKey) return false;

  try {
    const drafts = readRuntimeFormDrafts(storage, siteIdentifier);
    drafts[instanceKey] = {
      formId: String(draft?.formId || ""),
      draftName: String(draft?.draftName || "").trim().slice(0, 120),
      answers: draft?.answers && typeof draft.answers === "object" ? draft.answers : {},
      pageIndex: Math.max(0, Number(draft?.pageIndex) || 0),
      language: String(draft?.language || "en").slice(0, 12),
      savedAt: new Date(now).toISOString(),
      ...(draft?.draftId ? { draftId: String(draft.draftId) } : {}),
      ...(draft?.resumeToken ? { resumeToken: String(draft.resumeToken) } : {}),
    };
    storage.setItem(
      getStorageKey(siteIdentifier),
      JSON.stringify({ version: STORAGE_VERSION, drafts })
    );
    return true;
  } catch {
    return false;
  }
};

export const removeRuntimeFormDraft = (storage, siteIdentifier, instanceKey) => {
  if (!storage || !siteIdentifier || !instanceKey) return;

  try {
    const drafts = readRuntimeFormDrafts(storage, siteIdentifier);
    delete drafts[instanceKey];
    const key = getStorageKey(siteIdentifier);
    if (Object.keys(drafts).length) {
      storage.setItem(key, JSON.stringify({ version: STORAGE_VERSION, drafts }));
    } else {
      storage.removeItem(key);
    }
  } catch {
    // Saving progress is best-effort when browser storage is unavailable.
  }
};

