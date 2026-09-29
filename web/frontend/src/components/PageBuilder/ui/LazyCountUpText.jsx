import { lazy, Suspense } from "react";

const CountUpText = lazy(() => import("./CountUpText"));

export default function LazyCountUpText({ value, ...props }) {
  return (
    <Suspense fallback={<span className="count-up-number">{value}</span>}>
      <CountUpText value={value} {...props} />
    </Suspense>
  );
}
