export const MADAR_SERVICE_WORKER_PATH = "/madar-push-sw.js";
export const MADAR_SERVICE_WORKER_SCOPE = "/";

let registrationPromise = null;

export function serviceWorkersSupported(navigatorLike = globalThis.navigator) {
  return Boolean(navigatorLike?.serviceWorker?.register);
}

export function getMadarServiceWorkerRegistration(
  navigatorLike = globalThis.navigator
) {
  if (!serviceWorkersSupported(navigatorLike)) return Promise.resolve(null);
  if (registrationPromise) return registrationPromise;

  registrationPromise = (async () => {
    const existing = await navigatorLike.serviceWorker.getRegistration?.(
      MADAR_SERVICE_WORKER_SCOPE
    );
    if (existing) return existing;

    return navigatorLike.serviceWorker.register(MADAR_SERVICE_WORKER_PATH, {
      scope: MADAR_SERVICE_WORKER_SCOPE,
    });
  })().catch((error) => {
    registrationPromise = null;
    throw error;
  });

  return registrationPromise;
}

export async function getExistingMadarPushEndpoint(
  navigatorLike = globalThis.navigator
) {
  if (!serviceWorkersSupported(navigatorLike)) return null;
  const registration = await navigatorLike.serviceWorker.getRegistration?.(
    MADAR_SERVICE_WORKER_SCOPE
  );
  const subscription = await registration?.pushManager?.getSubscription?.();
  return subscription?.endpoint || null;
}
