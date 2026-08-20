import { lazy } from "react";

import RouteSuspense from "../../common/RouteSuspense";

const DataAnalysisWorkspace = lazy(() => import("../DataAnalysisWorkspace"));

export default function DataTab(props) {
  return (
    <RouteSuspense label="Loading data workspace" variant="data-analysis">
      <DataAnalysisWorkspace {...props} />
    </RouteSuspense>
  );
}
