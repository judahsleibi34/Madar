import { getPersistableProject } from "./PageBuilder.editorState";

const MISSING = Symbol("missing");
const hasOwn = (value, key) => Object.prototype.hasOwnProperty.call(value, key);
const isObject = (value) => Boolean(value && typeof value === "object" && !Array.isArray(value));

const cloneValue = (value) => {
  if (value === MISSING) return MISSING;
  if (Array.isArray(value)) return value.map(cloneValue);
  if (isObject(value)) {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, cloneValue(item)]));
  }
  return value;
};

export const builderValuesEqual = (left, right) => {
  if (left === right) return true;
  if (left === MISSING || right === MISSING) return false;
  if (Array.isArray(left) || Array.isArray(right)) {
    return Array.isArray(left) && Array.isArray(right) &&
      left.length === right.length &&
      left.every((item, index) => builderValuesEqual(item, right[index]));
  }
  if (isObject(left) || isObject(right)) {
    if (!isObject(left) || !isObject(right)) return false;
    const leftKeys = Object.keys(left).sort();
    const rightKeys = Object.keys(right).sort();
    return leftKeys.length === rightKeys.length &&
      leftKeys.every((key, index) =>
        key === rightKeys[index] && builderValuesEqual(left[key], right[key])
      );
  }
  return false;
};

const displayPath = (tokens = []) => tokens.reduce((path, token) => {
  if (token.kind === "property") return path ? `${path}.${token.key}` : token.key;
  if (token.kind === "entity") return `${path}[id=${token.id}]`;
  if (token.kind === "order") return `${path}.$order`;
  return path;
}, "");

const friendlyEntity = (value, id) => ({
  id: String(value?.id ?? id ?? ""),
  name: String(value?.name || value?.title || value?.label || value?.type || "").trim(),
  type: String(value?.type || "").trim(),
});

const makeConflict = ({ base, local, server, kind = "value", tokens, entity }) => ({
  path: displayPath(tokens),
  tokens: cloneValue(tokens),
  kind,
  entity: entity || null,
  baseValue: base === MISSING ? undefined : cloneValue(base),
  localValue: local === MISSING ? undefined : cloneValue(local),
  serverValue: server === MISSING ? undefined : cloneValue(server),
  localMissing: local === MISSING,
  serverMissing: server === MISSING,
});

const isIdArray = (...arrays) => {
  const items = arrays.flatMap((array) => Array.isArray(array) ? array : []);
  if (items.length === 0) return false;
  return items.every((item) => isObject(item) && String(item.id ?? "").trim());
};

const toIdMap = (array = []) => {
  const map = new Map();
  for (const item of array) {
    const id = String(item.id);
    if (map.has(id)) return null;
    map.set(id, item);
  }
  return map;
};

const sameIdOrder = (left, right) =>
  left.length === right.length && left.every((id, index) => id === right[index]);

const insertSideAdditions = (order, sideIds, resultIds) => {
  const next = [...order];
  sideIds.forEach((id, index) => {
    if (!resultIds.has(id) || next.includes(id)) return;
    const previous = [...sideIds.slice(0, index)].reverse().find((candidate) => next.includes(candidate));
    if (previous) {
      next.splice(next.indexOf(previous) + 1, 0, id);
      return;
    }
    const following = sideIds.slice(index + 1).find((candidate) => next.includes(candidate));
    if (following) next.splice(next.indexOf(following), 0, id);
    else next.push(id);
  });
  return next;
};

const mergeIdArray = ({ base, local, server, tokens, context }) => {
  const baseMap = toIdMap(base);
  const localMap = toIdMap(local);
  const serverMap = toIdMap(server);
  if (!baseMap || !localMap || !serverMap) {
    context.conflicts.push(makeConflict({ base, local, server, kind: "duplicate_id", tokens }));
    return cloneValue(server);
  }

  const result = new Map();
  const ids = new Set([...baseMap.keys(), ...localMap.keys(), ...serverMap.keys()]);
  for (const id of ids) {
    const baseItem = baseMap.has(id) ? baseMap.get(id) : MISSING;
    const localItem = localMap.has(id) ? localMap.get(id) : MISSING;
    const serverItem = serverMap.has(id) ? serverMap.get(id) : MISSING;
    const entityTokens = [...tokens, { kind: "entity", id }];
    const entity = friendlyEntity(localItem !== MISSING ? localItem : serverItem, id);

    if (baseItem === MISSING && localItem !== MISSING && serverItem !== MISSING &&
        !builderValuesEqual(localItem, serverItem)) {
      context.conflicts.push(makeConflict({
        base: MISSING,
        local: localItem,
        server: serverItem,
        kind: "concurrent_add",
        tokens: entityTokens,
        entity,
      }));
      result.set(id, cloneValue(serverItem));
      continue;
    }
    if (baseItem === MISSING && localItem !== MISSING && serverItem === MISSING) {
      result.set(id, cloneValue(localItem));
      context.appliedLocalChanges.push(displayPath(entityTokens));
      continue;
    }
    if (baseItem === MISSING && localItem === MISSING && serverItem !== MISSING) {
      result.set(id, cloneValue(serverItem));
      context.appliedServerChanges.push(displayPath(entityTokens));
      continue;
    }
    if (localItem === MISSING && serverItem === MISSING) continue;
    if (localItem === MISSING) {
      if (builderValuesEqual(serverItem, baseItem)) {
        context.appliedLocalChanges.push(displayPath(entityTokens));
        continue;
      }
      context.conflicts.push(makeConflict({
        base: baseItem,
        local: MISSING,
        server: serverItem,
        kind: "delete_modify",
        tokens: entityTokens,
        entity,
      }));
      result.set(id, cloneValue(serverItem));
      continue;
    }
    if (serverItem === MISSING) {
      if (builderValuesEqual(localItem, baseItem)) {
        context.appliedServerChanges.push(displayPath(entityTokens));
        continue;
      }
      context.conflicts.push(makeConflict({
        base: baseItem,
        local: localItem,
        server: MISSING,
        kind: "modify_delete",
        tokens: entityTokens,
        entity,
      }));
      continue;
    }
    if (baseItem === MISSING) {
      result.set(id, cloneValue(localItem));
      context.appliedLocalChanges.push(displayPath(entityTokens));
      continue;
    }
    result.set(id, mergeNode({
      base: baseItem,
      local: localItem,
      server: serverItem,
      tokens: entityTokens,
      context,
      entity,
    }));
  }

  const resultIds = new Set(result.keys());
  const baseIds = base.map((item) => String(item.id)).filter((id) => resultIds.has(id));
  const localIds = local.map((item) => String(item.id)).filter((id) => resultIds.has(id));
  const serverIds = server.map((item) => String(item.id)).filter((id) => resultIds.has(id));
  const commonBaseIds = baseIds.filter((id) => localMap.has(id) && serverMap.has(id));
  const localCommon = localIds.filter((id) => commonBaseIds.includes(id));
  const serverCommon = serverIds.filter((id) => commonBaseIds.includes(id));
  const baseCommon = baseIds.filter((id) => commonBaseIds.includes(id));
  const localReordered = !sameIdOrder(localCommon, baseCommon);
  const serverReordered = !sameIdOrder(serverCommon, baseCommon);

  let order = baseCommon;
  if (localReordered && !serverReordered) order = localCommon;
  else if (serverReordered && !localReordered) order = serverCommon;
  else if (localReordered && serverReordered) {
    if (sameIdOrder(localCommon, serverCommon)) order = localCommon;
    else {
      context.conflicts.push(makeConflict({
        base: baseIds,
        local: localIds,
        server: serverIds,
        kind: "order",
        tokens: [...tokens, { kind: "order" }],
      }));
      order = serverCommon;
    }
  }

  order = insertSideAdditions(order, localIds, resultIds);
  order = insertSideAdditions(order, serverIds, resultIds);
  for (const id of resultIds) if (!order.includes(id)) order.push(id);
  return order.map((id) => result.get(id));
};

const mergeNode = ({ base, local, server, tokens, context, entity = null }) => {
  if (builderValuesEqual(local, server)) return cloneValue(local);
  if (builderValuesEqual(local, base)) {
    context.appliedServerChanges.push(displayPath(tokens));
    return cloneValue(server);
  }
  if (builderValuesEqual(server, base)) {
    context.appliedLocalChanges.push(displayPath(tokens));
    return cloneValue(local);
  }

  if (isObject(base) && isObject(local) && isObject(server)) {
    const merged = {};
    const keys = [...new Set([...Object.keys(base), ...Object.keys(local), ...Object.keys(server)])].sort();
    for (const key of keys) {
      const value = mergeNode({
        base: hasOwn(base, key) ? base[key] : MISSING,
        local: hasOwn(local, key) ? local[key] : MISSING,
        server: hasOwn(server, key) ? server[key] : MISSING,
        tokens: [...tokens, { kind: "property", key }],
        context,
        entity,
      });
      if (value !== MISSING) merged[key] = value;
    }
    return merged;
  }

  if (Array.isArray(base) && Array.isArray(local) && Array.isArray(server) &&
      isIdArray(base, local, server)) {
    return mergeIdArray({ base, local, server, tokens, context });
  }

  context.conflicts.push(makeConflict({ base, local, server, tokens, entity }));
  return cloneValue(server);
};

export const mergeBuilderDraftSchemas = ({ baseSchema, localSchema, serverSchema } = {}) => {
  const base = getPersistableProject(baseSchema || {});
  const local = getPersistableProject(localSchema || {});
  const server = getPersistableProject(serverSchema || {});
  const context = { conflicts: [], appliedLocalChanges: [], appliedServerChanges: [] };
  const mergedSchema = mergeNode({ base, local, server, tokens: [], context });
  return {
    mergedSchema,
    conflicts: context.conflicts,
    appliedLocalChanges: [...new Set(context.appliedLocalChanges.filter(Boolean))],
    appliedServerChanges: [...new Set(context.appliedServerChanges.filter(Boolean))],
  };
};

const findEntityIndex = (array, id) => array.findIndex((item) => String(item?.id) === String(id));

const applyConflictValue = (root, conflict, choice) => {
  const chosenMissing = choice === "local" ? conflict.localMissing : conflict.serverMissing;
  const chosen = choice === "local" ? conflict.localValue : conflict.serverValue;
  const tokens = conflict.tokens || [];
  if (tokens.length === 0) return chosenMissing ? {} : cloneValue(chosen);

  let cursor = root;
  for (let index = 0; index < tokens.length - 1; index += 1) {
    const token = tokens[index];
    if (token.kind === "property") cursor = cursor?.[token.key];
    else if (token.kind === "entity") cursor = cursor?.[findEntityIndex(cursor, token.id)];
    if (cursor === undefined || cursor === null) return root;
  }
  const last = tokens[tokens.length - 1];
  if (last.kind === "property") {
    if (chosenMissing) delete cursor[last.key];
    else cursor[last.key] = cloneValue(chosen);
  } else if (last.kind === "entity" && Array.isArray(cursor)) {
    const entityIndex = findEntityIndex(cursor, last.id);
    if (chosenMissing && entityIndex >= 0) cursor.splice(entityIndex, 1);
    else if (!chosenMissing && entityIndex >= 0) cursor[entityIndex] = cloneValue(chosen);
    else if (!chosenMissing) cursor.push(cloneValue(chosen));
  } else if (last.kind === "order" && Array.isArray(cursor)) {
    const chosenOrder = Array.isArray(chosen) ? chosen.map(String) : [];
    const byId = new Map(cursor.map((item) => [String(item?.id), item]));
    cursor.splice(0, cursor.length,
      ...chosenOrder.filter((id) => byId.has(id)).map((id) => byId.get(id)),
      ...cursor.filter((item) => !chosenOrder.includes(String(item?.id)))
    );
  }
  return root;
};

export const resolveBuilderDraftConflicts = ({ mergedSchema, conflicts = [], resolutions = {} } = {}) => {
  let resolved = cloneValue(getPersistableProject(mergedSchema || {}));
  conflicts.forEach((conflict, index) => {
    const choice = resolutions[index] || resolutions[conflict.path];
    if (choice === "local" || choice === "server") {
      resolved = applyConflictValue(resolved, conflict, choice);
    }
  });
  return resolved;
};

export const resolveBuilderDraftConflictsPreferLocal = ({ mergeResult, pathPrefix } = {}) => {
  const conflicts = Array.isArray(mergeResult?.conflicts) ? mergeResult.conflicts : [];
  const prefix = String(pathPrefix || "").trim();
  if (
    !prefix ||
    conflicts.length === 0 ||
    conflicts.some(({ path }) => path !== prefix && !String(path || "").startsWith(`${prefix}.`))
  ) return null;

  return resolveBuilderDraftConflicts({
    mergedSchema: mergeResult.mergedSchema,
    conflicts,
    resolutions: Object.fromEntries(conflicts.map((_, index) => [index, "local"])),
  });
};
