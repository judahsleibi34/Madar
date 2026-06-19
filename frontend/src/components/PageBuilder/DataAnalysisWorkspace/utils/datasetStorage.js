const DATABASE_NAME = "madar-sensitive-data";
const DATABASE_VERSION = 1;
const STORE_NAME = "datasets";
const DEFAULT_SCOPE = "current-dataset";

const openDatabase = () =>
  new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      reject(new Error("IndexedDB is not available in this browser."));
      return;
    }

    const request = indexedDB.open(DATABASE_NAME, DATABASE_VERSION);
    request.onupgradeneeded = () => {
      const database = request.result;
      if (!database.objectStoreNames.contains(STORE_NAME)) {
        database.createObjectStore(STORE_NAME);
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error("Could not open local dataset storage."));
  });

const runRequest = async (mode, operation) => {
  const database = await openDatabase();
  try {
    return await new Promise((resolve, reject) => {
      const transaction = database.transaction(STORE_NAME, mode);
      const store = transaction.objectStore(STORE_NAME);
      const request = operation(store);
      let result;
      request.onsuccess = () => {
        result = request.result;
      };
      request.onerror = () => reject(request.error || new Error("Local dataset storage failed."));
      transaction.oncomplete = () => resolve(result);
      transaction.onabort = () => reject(transaction.error || new Error("Local dataset storage was cancelled."));
    });
  } finally {
    database.close();
  }
};

const bytesToBase64 = (bytes) => {
  let binary = "";
  const chunkSize = 0x8000;
  for (let index = 0; index < bytes.length; index += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(index, index + chunkSize));
  }
  return btoa(binary);
};

const base64ToBytes = (value) => {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  return bytes;
};

const deriveEncryptionKey = async (password, salt, usages) => {
  const material = await globalThis.crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(password),
    "PBKDF2",
    false,
    ["deriveKey"]
  );
  return globalThis.crypto.subtle.deriveKey(
    { name: "PBKDF2", salt, iterations: 250000, hash: "SHA-256" },
    material,
    { name: "AES-GCM", length: 256 },
    false,
    usages
  );
};

const serializeForEncryption = async (value) => {
  if (value instanceof File) {
    return {
      kind: "file",
      name: value.name,
      type: value.type,
      lastModified: value.lastModified,
      bytes: bytesToBase64(new Uint8Array(await value.arrayBuffer())),
    };
  }
  if (value instanceof Blob) {
    return {
      kind: "blob",
      type: value.type,
      bytes: bytesToBase64(new Uint8Array(await value.arrayBuffer())),
    };
  }
  if (Array.isArray(value)) {
    return { kind: "array", value: await Promise.all(value.map(serializeForEncryption)) };
  }
  if (value && typeof value === "object") {
    const entries = await Promise.all(
      Object.entries(value).map(async ([key, item]) => [key, await serializeForEncryption(item)])
    );
    return { kind: "object", value: Object.fromEntries(entries) };
  }
  return { kind: "json", value };
};

const deserializeEncryptedValue = (payload) => {
  if (payload.kind === "file") {
    return new File([base64ToBytes(payload.bytes)], payload.name, {
      type: payload.type,
      lastModified: payload.lastModified,
    });
  }
  if (payload.kind === "blob") return new Blob([base64ToBytes(payload.bytes)], { type: payload.type });
  if (payload.kind === "array") return payload.value.map(deserializeEncryptedValue);
  if (payload.kind === "object") {
    return Object.fromEntries(
      Object.entries(payload.value).map(([key, value]) => [key, deserializeEncryptedValue(value)])
    );
  }
  return payload.value;
};

const encryptValue = async (value, password) => {
  if (!globalThis.crypto?.subtle) throw new Error("Browser encryption is unavailable.");
  const salt = globalThis.crypto.getRandomValues(new Uint8Array(16));
  const iv = globalThis.crypto.getRandomValues(new Uint8Array(12));
  const key = await deriveEncryptionKey(password, salt, ["encrypt"]);
  const plaintext = new TextEncoder().encode(JSON.stringify(await serializeForEncryption(value)));
  const ciphertext = await globalThis.crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, plaintext);
  return {
    encrypted: true,
    salt: bytesToBase64(salt),
    iv: bytesToBase64(iv),
    ciphertext: bytesToBase64(new Uint8Array(ciphertext)),
  };
};

const decryptValue = async (record, password) => {
  if (!password) throw new Error("A password is required to unlock the saved dataset.");
  const salt = base64ToBytes(record.salt);
  const iv = base64ToBytes(record.iv);
  const key = await deriveEncryptionKey(password, salt, ["decrypt"]);
  const plaintext = await globalThis.crypto.subtle.decrypt(
    { name: "AES-GCM", iv },
    key,
    base64ToBytes(record.ciphertext)
  );
  return deserializeEncryptedValue(JSON.parse(new TextDecoder().decode(plaintext)));
};

export async function saveDataset(fileOrData, options = {}) {
  const scope = options.scope || DEFAULT_SCOPE;
  const payload = options.password
    ? await encryptValue(fileOrData, options.password)
    : { encrypted: false, value: fileOrData };
  await runRequest("readwrite", (store) =>
    store.put({ ...payload, savedAt: Date.now(), version: 1 }, scope)
  );
}

export async function loadDataset(options = {}) {
  const scope = options.scope || DEFAULT_SCOPE;
  const record = await runRequest("readonly", (store) => store.get(scope));
  if (!record) return null;
  return record.encrypted ? decryptValue(record, options.password) : record.value;
}

export async function clearDataset(options = {}) {
  const scope = options.scope || DEFAULT_SCOPE;
  await runRequest("readwrite", (store) => store.delete(scope));
}
