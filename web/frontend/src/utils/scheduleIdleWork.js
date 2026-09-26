export function scheduleIdleWork(callback, { timeout = 2000 } = {}) {
  let cancelled = false;
  let idleHandle = null;
  let firstFrame = null;
  let secondFrame = null;

  const run = () => {
    if (!cancelled) callback();
  };

  if (typeof globalThis.requestIdleCallback === "function") {
    idleHandle = globalThis.requestIdleCallback(run, { timeout });
  } else if (typeof globalThis.requestAnimationFrame === "function") {
    firstFrame = globalThis.requestAnimationFrame(() => {
      secondFrame = globalThis.requestAnimationFrame(run);
    });
  } else {
    globalThis.queueMicrotask(run);
  }

  return () => {
    cancelled = true;
    if (idleHandle !== null && typeof globalThis.cancelIdleCallback === "function") {
      globalThis.cancelIdleCallback(idleHandle);
    }
    if (typeof globalThis.cancelAnimationFrame === "function") {
      if (firstFrame !== null) globalThis.cancelAnimationFrame(firstFrame);
      if (secondFrame !== null) globalThis.cancelAnimationFrame(secondFrame);
    }
  };
}
