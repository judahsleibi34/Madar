const isPlainObject = (value) => {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
};

const unsupportedValueError = (value, path) =>
  new TypeError(`Unsupported builder schema value at ${path}: ${typeof value}`);

/**
 * Canonical Page Builder schema semantics:
 * - plain-object keys are sorted recursively;
 * - array order remains significant;
 * - undefined object properties are omitted, matching JSON object semantics;
 * - undefined array entries and non-finite numbers become null;
 * - negative zero becomes zero and Date values become ISO strings;
 * - functions, symbols, bigint values, non-plain objects, and cycles are rejected.
 *
 * This function is identity-only. It never migrates, repairs, defaults, removes
 * unknown fields, or generates IDs, slugs, or timestamps.
 */
export const canonicalizeBuilderSchema = (value, { path = "$", ancestors = new Set() } = {}) => {
  if (value === null) return null;
  if (value instanceof Date) {
    const timestamp = value.toJSON();
    if (timestamp === null) throw new TypeError(`Invalid Date in builder schema at ${path}`);
    return timestamp;
  }

  const type = typeof value;
  if (type === "string" || type === "boolean") return value;
  if (type === "number") {
    if (!Number.isFinite(value)) return null;
    return Object.is(value, -0) ? 0 : value;
  }
  if (type === "undefined") return undefined;
  if (type !== "object") throw unsupportedValueError(value, path);
  if (ancestors.has(value)) throw new TypeError(`Cyclic builder schema value at ${path}`);

  const nextAncestors = new Set(ancestors);
  nextAncestors.add(value);

  if (Array.isArray(value)) {
    return value.map((item, index) => {
      const canonical = canonicalizeBuilderSchema(item, {
        path: `${path}[${index}]`,
        ancestors: nextAncestors,
      });
      return canonical === undefined ? null : canonical;
    });
  }

  if (!isPlainObject(value)) {
    throw new TypeError(`Unsupported builder schema object at ${path}`);
  }

  const entries = [];
  Object.keys(value).sort().forEach((key) => {
    const canonical = canonicalizeBuilderSchema(value[key], {
      path: `${path}.${key}`,
      ancestors: nextAncestors,
    });
    if (canonical !== undefined) entries.push([key, canonical]);
  });
  return Object.fromEntries(entries);
};

export const serializeBuilderSchema = (value) => {
  const canonical = canonicalizeBuilderSchema(value);
  return JSON.stringify(canonical === undefined ? null : canonical);
};

// 64-bit FNV-1a is deterministic, browser-compatible, and sufficient for
// in-memory dirty/recovery identity. Equality still uses canonical serialization.
export const hashBuilderSchema = (value) => {
  const input = serializeBuilderSchema(value);
  let hash = 0xcbf29ce484222325n;
  for (let index = 0; index < input.length; index += 1) {
    hash ^= BigInt(input.charCodeAt(index));
    hash = BigInt.asUintN(64, hash * 0x100000001b3n);
  }
  return `fnv1a64-${hash.toString(16).padStart(16, "0")}`;
};

export const areBuilderSchemasEqual = (left, right) =>
  serializeBuilderSchema(left) === serializeBuilderSchema(right);
