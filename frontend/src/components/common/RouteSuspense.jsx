import { Suspense, useEffect, useState } from "react";

import PageSkeleton from "./PageSkeleton";

function DelayedFallback({
  delay = 160,
  fallback,
  label,
  lang,
  variant,
}) {
  const [showFallback, setShowFallback] = useState(delay <= 0);

  useEffect(() => {
    if (delay <= 0) {
      return undefined;
    }

    const timeoutId = window.setTimeout(() => {
      setShowFallback(true);
    }, delay);

    return () => window.clearTimeout(timeoutId);
  }, [delay]);

  if (!showFallback) return null;

  return fallback || <PageSkeleton label={label} lang={lang} variant={variant} />;
}

export default function RouteSuspense({
  children,
  delay,
  fallback,
  label,
  lang,
  variant = "default",
}) {
  return (
    <Suspense
      fallback={
        <DelayedFallback
          delay={delay}
          fallback={fallback}
          label={label}
          lang={lang}
          variant={variant}
        />
      }
    >
      {children}
    </Suspense>
  );
}
