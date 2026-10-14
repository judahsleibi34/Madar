// A page whose JavaScript module failed to load (for example after a new
// deploy replaced the files, or a dev-server cache hiccup) cannot recover by
// re-rendering: the browser keeps the failed import. One full reload fixes it.
const MODULE_ERROR = /Failed to fetch dynamically imported module|error loading dynamically imported module|Importing a module script failed|does not provide an export named|Unable to preload CSS|Loading (CSS )?chunk [\w-]+ failed|ChunkLoadError/i;
const KEY = "madar.moduleReloadAt";
const WINDOW_MS = 60_000;

export const isModuleLoadError = error => MODULE_ERROR.test(String(error?.message || error || "")) || error?.name === "ChunkLoadError";

/** Reload at most once per minute so a genuinely broken page can never loop. */
export function reloadOnce({ storage = globalThis.sessionStorage, now = Date.now(), reload = () => globalThis.location.reload() } = {}) {
  let last = 0;
  try { last = Number(storage?.getItem(KEY)) || 0; } catch { /* Storage may be unavailable. */ }
  if (now - last < WINDOW_MS) return false;
  try { storage?.setItem(KEY, String(now)); } catch { /* Reload anyway. */ }
  reload();
  return true;
}

export function installModuleReload(target = globalThis.window) {
  target?.addEventListener?.("vite:preloadError", event => { if (reloadOnce()) event.preventDefault(); });
}
