const DATABASE_NAME = "madar-push-lifecycle";
const STORE_NAME = "state";
const ROTATION_KEY = "rotation-needed";

function openDatabase(indexedDbLike = globalThis.indexedDB) {
  if (!indexedDbLike?.open) return Promise.resolve(null);
  return new Promise((resolve, reject) => {
    const request = indexedDbLike.open(DATABASE_NAME, 1);
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains(STORE_NAME)) {
        request.result.createObjectStore(STORE_NAME);
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function readPushRotationNeeded(indexedDbLike = globalThis.indexedDB) {
  const database = await openDatabase(indexedDbLike);
  if (!database) return false;
  try {
    return await new Promise((resolve, reject) => {
      const request = database.transaction(STORE_NAME, "readonly")
        .objectStore(STORE_NAME)
        .get(ROTATION_KEY);
      request.onsuccess = () => resolve(request.result?.needed === true);
      request.onerror = () => reject(request.error);
    });
  } finally {
    database.close();
  }
}

export async function clearPushRotationNeeded(indexedDbLike = globalThis.indexedDB) {
  const database = await openDatabase(indexedDbLike);
  if (!database) return false;
  try {
    await new Promise((resolve, reject) => {
      const transaction = database.transaction(STORE_NAME, "readwrite");
      transaction.objectStore(STORE_NAME).delete(ROTATION_KEY);
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error);
      transaction.onabort = () => reject(transaction.error);
    });
    return true;
  } finally {
    database.close();
  }
}
