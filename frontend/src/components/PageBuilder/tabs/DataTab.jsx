import { lazy, Suspense } from "react";

const DataAnalysisWorkspace = lazy(() => import("../DataAnalysisWorkspace"));

export default function DataTab(props) {
  return (
    <Suspense
      fallback={
        <div className="builder-panel-loading" role="status" aria-live="polite">
          Loading data workspace...
        </div>
      }
    >
      <DataAnalysisWorkspace {...props} />
    </Suspense>
  );
}
