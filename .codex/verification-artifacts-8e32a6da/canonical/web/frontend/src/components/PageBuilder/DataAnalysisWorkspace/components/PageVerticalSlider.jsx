import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const SCROLL_SELECTORS = [
  ".builder-canvas-shell",
  ".builder-sidebar",
  ".builder-inspector",
  ".admin-dashboard-page",
  ".page-builder-dashboard-page",
  ".admin-dashboard-layout",
  ".page-builder",
  ".builder-desktop-shell",
  ".builder-layout",
  ".daw-page",
  "#root",
];

function getDocumentScroller() {
  return document.scrollingElement || document.documentElement || document.body;
}

function isDocumentTarget(target) {
  const documentScroller = getDocumentScroller();

  return (
    target === window ||
    target === document ||
    target === documentScroller ||
    target === document.documentElement ||
    target === document.body
  );
}

function getDocumentScrollInfo() {
  const scroller = getDocumentScroller();

  const scrollTop =
    window.scrollY ||
    scroller.scrollTop ||
    document.documentElement.scrollTop ||
    document.body.scrollTop ||
    0;

  const scrollHeight = Math.max(
    scroller.scrollHeight || 0,
    document.documentElement.scrollHeight || 0,
    document.body.scrollHeight || 0
  );

  const clientHeight =
    window.innerHeight ||
    scroller.clientHeight ||
    document.documentElement.clientHeight ||
    0;

  const maxScroll = Math.max(scrollHeight - clientHeight, 0);

  return {
    target: scroller,
    isDocument: true,
    scrollTop,
    scrollHeight,
    clientHeight,
    maxScroll,
  };
}

function getElementScrollInfo(element) {
  if (!element || isDocumentTarget(element)) {
    return getDocumentScrollInfo();
  }

  return {
    target: element,
    isDocument: false,
    scrollTop: element.scrollTop || 0,
    scrollHeight: element.scrollHeight || 0,
    clientHeight: element.clientHeight || 0,
    maxScroll: Math.max((element.scrollHeight || 0) - (element.clientHeight || 0), 0),
  };
}

function hasScrollableOverflow(element) {
  if (!element || isDocumentTarget(element)) {
    return true;
  }

  const styles = window.getComputedStyle(element);
  const overflowY = styles.overflowY;

  return (
    overflowY === "auto" ||
    overflowY === "scroll" ||
    overflowY === "overlay"
  );
}

function canElementActuallyScroll(element) {
  if (!element || isDocumentTarget(element)) {
    return getDocumentScrollInfo().maxScroll > 4;
  }

  if (!hasScrollableOverflow(element)) {
    return false;
  }

  const info = getElementScrollInfo(element);

  return info.maxScroll > 4;
}

function getCandidateElements() {
  const selectorElements = SCROLL_SELECTORS.flatMap((selector) =>
    Array.from(document.querySelectorAll(selector))
  );

  const candidates = [
    getDocumentScroller(),
    document.documentElement,
    document.body,
    ...selectorElements,
  ].filter(Boolean);

  return Array.from(new Set(candidates));
}

function findBestScrollTarget() {
  const documentInfo = getDocumentScrollInfo();

  const elementCandidates = getCandidateElements()
    .filter((element) => !isDocumentTarget(element))
    .filter(canElementActuallyScroll)
    .map(getElementScrollInfo)
    .filter((info) => info.maxScroll > 4)
    .sort((a, b) => b.maxScroll - a.maxScroll);

  const builderCanvas = elementCandidates.find((info) =>
    info.target.classList?.contains("builder-canvas-shell")
  );

  if (builderCanvas) {
    return builderCanvas.target;
  }

  if (documentInfo.maxScroll > 4) {
    return documentInfo.target;
  }

  return elementCandidates[0]?.target || documentInfo.target;
}

function getActiveScrollInfo(target) {
  if (!target || isDocumentTarget(target)) {
    return getDocumentScrollInfo();
  }

  if (!canElementActuallyScroll(target)) {
    const nextTarget = findBestScrollTarget();
    return getElementScrollInfo(nextTarget);
  }

  return getElementScrollInfo(target);
}

function scrollTargetTo(target, top) {
  const safeTop = Math.max(0, Number.isFinite(top) ? top : 0);

  if (!target || isDocumentTarget(target)) {
    const scroller = getDocumentScroller();

    window.scrollTo({
      top: safeTop,
      behavior: "auto",
    });

    scroller.scrollTop = safeTop;
    document.documentElement.scrollTop = safeTop;
    document.body.scrollTop = safeTop;

    return;
  }

  target.scrollTop = safeTop;

  if (typeof target.scrollTo === "function") {
    target.scrollTo({
      top: safeTop,
      behavior: "auto",
    });
  }
}

function scrollTargetBy(target, amount) {
  const info = getActiveScrollInfo(target);
  scrollTargetTo(info.target, info.scrollTop + amount);
}

export default function PageVerticalSlider() {
  const trackRef = useRef(null);
  const scrollTargetRef = useRef(null);
  const isDraggingRef = useRef(false);
  const animationFrameRef = useRef(null);
  const refreshTimeoutRef = useRef(null);

  const [thumbTop, setThumbTop] = useState(0);
  const [thumbHeight, setThumbHeight] = useState(56);
  const [percentage, setPercentage] = useState(0);

  const debugEnabled = useMemo(() => {
    return window.location.search.includes("debugSlider=true");
  }, []);

  const debugTargets = useCallback(() => {
    if (!debugEnabled) return;

    const rows = getCandidateElements().map((element) => {
      const info = getElementScrollInfo(element);
      const styles = isDocumentTarget(element)
        ? null
        : window.getComputedStyle(element);

      return {
        target: isDocumentTarget(element)
          ? "document"
          : `${element.tagName?.toLowerCase() || "element"}${
              element.id ? `#${element.id}` : ""
            }${
              typeof element.className === "string"
                ? `.${element.className.split(" ").filter(Boolean).join(".")}`
                : ""
            }`,
        overflowY: styles?.overflowY || "document",
        scrollTop: info.scrollTop,
        scrollHeight: info.scrollHeight,
        clientHeight: info.clientHeight,
        maxScroll: info.maxScroll,
        usable: canElementActuallyScroll(element),
      };
    });

    console.table(rows);
  }, [debugEnabled]);

  const resolveScrollTarget = useCallback(() => {
    const currentTarget = scrollTargetRef.current;
    const currentInfo = getActiveScrollInfo(currentTarget);

    if (currentInfo.maxScroll > 4) {
      scrollTargetRef.current = currentInfo.target;
      return currentInfo;
    }

    const nextTarget = findBestScrollTarget();
    const nextInfo = getActiveScrollInfo(nextTarget);

    scrollTargetRef.current = nextInfo.target;

    return nextInfo;
  }, []);

  const updateThumb = useCallback(() => {
    const info = resolveScrollTarget();

    const track = trackRef.current;
    const trackHeight =
      track?.getBoundingClientRect().height || window.innerHeight || 1;

    const minThumbHeight = 34;

    const nextThumbHeight =
      info.maxScroll > 0
        ? Math.max(
            minThumbHeight,
            Math.min(
              trackHeight,
              (info.clientHeight / Math.max(info.scrollHeight, 1)) * trackHeight
            )
          )
        : 56;

    const availableTrack = Math.max(trackHeight - nextThumbHeight, 1);

    const nextThumbTop =
      info.maxScroll > 0
        ? (info.scrollTop / info.maxScroll) * availableTrack
        : 0;

    const nextPercentage =
      info.maxScroll > 0
        ? Math.round((info.scrollTop / info.maxScroll) * 100)
        : 0;

    setThumbHeight(Number.isFinite(nextThumbHeight) ? nextThumbHeight : 56);
    setThumbTop(Number.isFinite(nextThumbTop) ? nextThumbTop : 0);
    setPercentage(Number.isFinite(nextPercentage) ? nextPercentage : 0);
  }, [resolveScrollTarget]);

  const scheduleUpdate = useCallback(() => {
    if (animationFrameRef.current) return;

    animationFrameRef.current = window.requestAnimationFrame(() => {
      animationFrameRef.current = null;
      updateThumb();
    });
  }, [updateThumb]);

  const refreshScrollTarget = useCallback(() => {
    if (refreshTimeoutRef.current) {
      window.clearTimeout(refreshTimeoutRef.current);
    }

    refreshTimeoutRef.current = window.setTimeout(() => {
      scrollTargetRef.current = findBestScrollTarget();
      debugTargets();
      scheduleUpdate();
    }, 40);
  }, [debugTargets, scheduleUpdate]);

  const scrollToPointer = useCallback(
    (clientY) => {
      const track = trackRef.current;
      if (!track) return;

      const info = resolveScrollTarget();
      const rect = track.getBoundingClientRect();

      const y = clientY - rect.top;
      const availableTrack = Math.max(rect.height - thumbHeight, 1);

      const nextThumbTop = Math.min(
        Math.max(y - thumbHeight / 2, 0),
        availableTrack
      );

      const percent = nextThumbTop / availableTrack;
      const nextScrollTop = info.maxScroll * percent;

      scrollTargetTo(info.target, nextScrollTop);
      scheduleUpdate();
    },
    [resolveScrollTarget, scheduleUpdate, thumbHeight]
  );

  const handlePointerDown = useCallback(
    (event) => {
      event.preventDefault();
      event.stopPropagation();

      isDraggingRef.current = true;
      scrollToPointer(event.clientY);

      if (trackRef.current?.setPointerCapture) {
        trackRef.current.setPointerCapture(event.pointerId);
      }

      const handlePointerMove = (moveEvent) => {
        if (!isDraggingRef.current) return;

        moveEvent.preventDefault();
        scrollToPointer(moveEvent.clientY);
      };

      const handlePointerUp = () => {
        isDraggingRef.current = false;

        window.removeEventListener("pointermove", handlePointerMove);
        window.removeEventListener("pointerup", handlePointerUp);
        window.removeEventListener("pointercancel", handlePointerUp);
      };

      window.addEventListener("pointermove", handlePointerMove, {
        passive: false,
      });

      window.addEventListener("pointerup", handlePointerUp);
      window.addEventListener("pointercancel", handlePointerUp);
    },
    [scrollToPointer]
  );

  const handleWheel = useCallback(
    (event) => {
      event.preventDefault();
      event.stopPropagation();

      const info = resolveScrollTarget();
      scrollTargetBy(info.target, event.deltaY);
      scheduleUpdate();
    },
    [resolveScrollTarget, scheduleUpdate]
  );

  const handleKeyDown = useCallback(
    (event) => {
      const info = resolveScrollTarget();

      if (event.key === "ArrowUp") {
        event.preventDefault();
        scrollTargetBy(info.target, -80);
      }

      if (event.key === "ArrowDown") {
        event.preventDefault();
        scrollTargetBy(info.target, 80);
      }

      if (event.key === "PageUp") {
        event.preventDefault();
        scrollTargetBy(info.target, -window.innerHeight * 0.85);
      }

      if (event.key === "PageDown") {
        event.preventDefault();
        scrollTargetBy(info.target, window.innerHeight * 0.85);
      }

      if (event.key === "Home") {
        event.preventDefault();
        scrollTargetTo(info.target, 0);
      }

      if (event.key === "End") {
        event.preventDefault();
        scrollTargetTo(info.target, info.maxScroll);
      }

      scheduleUpdate();
    },
    [resolveScrollTarget, scheduleUpdate]
  );

  useEffect(() => {
    scrollTargetRef.current = findBestScrollTarget();
    debugTargets();
    updateThumb();

    const handleScroll = () => {
      scheduleUpdate();
    };

    const handleResize = () => {
      refreshScrollTarget();
    };

    const attachScrollListeners = () => {
      const candidates = getCandidateElements();

      window.addEventListener("scroll", handleScroll, {
        passive: true,
      });

      candidates.forEach((element) => {
        if (isDocumentTarget(element)) return;

        element.addEventListener("scroll", handleScroll, {
          passive: true,
        });
      });

      return () => {
        window.removeEventListener("scroll", handleScroll);

        candidates.forEach((element) => {
          if (isDocumentTarget(element)) return;

          element.removeEventListener("scroll", handleScroll);
        });
      };
    };

    let removeScrollListeners = attachScrollListeners();

    window.addEventListener("resize", handleResize);

    const observer = new MutationObserver(() => {
      refreshScrollTarget();

      if (removeScrollListeners) {
        removeScrollListeners();
      }

      removeScrollListeners = attachScrollListeners();
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["class", "style"],
    });

    let resizeObserver = null;

    if ("ResizeObserver" in window) {
      resizeObserver = new ResizeObserver(refreshScrollTarget);

      [
        document.body,
        document.documentElement,
        document.querySelector("#root"),
        document.querySelector(".admin-dashboard-page"),
        document.querySelector(".page-builder-dashboard-page"),
        document.querySelector(".admin-dashboard-layout"),
        document.querySelector(".page-builder"),
        document.querySelector(".builder-canvas-shell"),
      ]
        .filter(Boolean)
        .forEach((element) => resizeObserver.observe(element));
    }

    const intervalId = window.setInterval(refreshScrollTarget, 900);

    return () => {
      if (removeScrollListeners) {
        removeScrollListeners();
      }

      window.removeEventListener("resize", handleResize);
      window.clearInterval(intervalId);

      observer.disconnect();

      if (resizeObserver) {
        resizeObserver.disconnect();
      }

      if (animationFrameRef.current) {
        window.cancelAnimationFrame(animationFrameRef.current);
      }

      if (refreshTimeoutRef.current) {
        window.clearTimeout(refreshTimeoutRef.current);
      }
    };
  }, [
    debugTargets,
    refreshScrollTarget,
    scheduleUpdate,
    updateThumb,
  ]);

  return (
    <aside className="daw-normal-slider" aria-label="Page scroll slider">
      <div
        ref={trackRef}
        className="daw-normal-slider-track"
        role="slider"
        tabIndex={0}
        aria-label="Scroll page"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percentage}
        onPointerDown={handlePointerDown}
        onWheel={handleWheel}
        onKeyDown={handleKeyDown}
      >
        <span
          className="daw-normal-slider-thumb"
          style={{
            top: `${thumbTop}px`,
            height: `${thumbHeight}px`,
          }}
        />
      </div>
    </aside>
  );
}