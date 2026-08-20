export function normalizeRuntimeAnswerValue(value) {
  if (Array.isArray(value)) {
    return value.map(normalizeRuntimeAnswerValue);
  }

  if (value && typeof value === "object" && "value" in value) {
    return value.value;
  }

  return value;
}

export function deferEffectStateUpdate(callback) {
  let cancelled = false;

  queueMicrotask(() => {
    if (!cancelled) callback();
  });

  return () => {
    cancelled = true;
  };
}
