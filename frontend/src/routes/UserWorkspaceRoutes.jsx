import { lazy } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import RouteSuspense from "../components/common/RouteSuspense";
import { getBuilderProjectIdFromPath } from "../components/PageBuilder/core/PageBuilder.workspaceRouting";
import { appShellContent } from "../content";
import { DashboardLoadingElement, DashboardShell, RestrictedAccessWindow } from "./shared";

const ChangePasswordPage = lazy(() => import("../components/DashboardBuilder/ChangePasswordPage"));
const SettingsPage = lazy(() => import("../components/DashboardBuilder/SettingsPage"));
const UserDashboard = lazy(() => import("../components/DashboardBuilder/UserDashboard"));
const MyPlanPage = lazy(() => import("../components/DashboardBuilder/MyPlanPage"));
const NotificationsPage = lazy(() => import("../components/DashboardBuilder/NotificationsPage"));
const ArchivePage = lazy(() => import("../components/DashboardBuilder/ArchivePage"));
const EcommercePage = lazy(() => import("../components/DashboardBuilder/EcommercePage"));
const EcommerceStorePage = lazy(() => import("../components/DashboardBuilder/EcommerceStorePage"));
const ReservationCalendarPage = lazy(() =>
  import("../components/DashboardBuilder/ReservationCalendarPage")
);
const BuilderFormPreviewPage = lazy(() =>
  import("../components/PageBuilder/preview/BuilderFormPreviewPage")
);
const TenantSiteRuntime = lazy(() =>
  import("../components/PageBuilder/runtime/TenantSiteRuntime")
);
const PageBuilder = lazy(() => import("../components/PageBuilder"));
const BuilderProjectChooser = lazy(() =>
  import("../components/PageBuilder/workspace/BuilderProjectChooser")
);

function BuilderWorkspaceEntry({ workspace = "page-builder", ...pageBuilderProps }) {
  const location = useLocation();
  const projectId = getBuilderProjectIdFromPath(location.pathname);
  if (!projectId) {
    return (
      <BuilderProjectChooser
        workspace={workspace}
        autoEnterProject={workspace === "page-builder"}
        autoOpenSingleProject
      />
    );
  }
  return <PageBuilder key={`${workspace}:${projectId}`} {...pageBuilderProps} />;
}

export default function UserWorkspaceRoutes({
  lang,
  onGoToDashboard,
  onUserUpdated,
  shellProps,
  themeMode,
  user,
}) {
  const location = useLocation();
  const isBuilderLoadingPath =
    location.pathname.startsWith("/page-builder") ||
    location.pathname.startsWith("/builder-responses") ||
    location.pathname.startsWith("/builder-data") ||
    location.pathname.startsWith("/calendar") ||
    location.pathname.startsWith("/archive");

  const renderShell = (children, options = {}) => (
    <DashboardShell
      {...shellProps}
      compactSidebar={options.compactSidebar}
      hideLanguage={options.hideLanguage}
      isPageBuilderShell={options.isPageBuilderShell}
      shellLang={options.lang}
    >
      {children}
    </DashboardShell>
  );

  const renderRestrictedPage = (message) =>
    renderShell(
      <RestrictedAccessWindow
        title={appShellContent.restrictedAccess.title}
        message={message}
        actionLabel={appShellContent.restrictedAccess.actionLabel}
        onAction={onGoToDashboard}
      />
    );

  return (
    <RouteSuspense
      fallback={
        isBuilderLoadingPath
          ? renderShell(
              <DashboardLoadingElement pathname={location.pathname} lang={lang} />,
              {
                compactSidebar:
                  location.pathname.startsWith("/builder-responses") ||
                  location.pathname.startsWith("/builder-data") ||
                  location.pathname.startsWith("/archive"),
                isPageBuilderShell: location.pathname.startsWith("/page-builder"),
                lang: location.pathname.startsWith("/page-builder") ? "en" : lang,
              }
            )
          : <DashboardLoadingElement pathname={location.pathname} lang={lang} />
      }
      lang={lang}
      variant={isBuilderLoadingPath ? "builder" : "dashboard"}
    >
      <Routes>
      <Route
        path="/dashboard/*"
        element={renderShell(
          <UserDashboard
            lang={lang}
            user={user}
            themeMode={themeMode}
            onThemeModeChange={shellProps.onThemeModeChange}
          />
        )}
      />

      <Route
        path="/page-builder/projects/:projectId/form-preview/:formId"
        element={<BuilderFormPreviewPage user={user} />}
      />

      <Route
        path="/page-builder/projects/:projectId/preview/*"
        element={<TenantSiteRuntime draftPreview user={user} />}
      />

      <Route
        path="/page-builder/*"
        element={renderShell(
          <BuilderWorkspaceEntry
            workspace="page-builder"
            user={user}
            templateLang={lang}
            appThemeMode={themeMode}
            onAppThemeModeChange={shellProps.onThemeModeChange}
          />,
          { isPageBuilderShell: true, lang: "en" }
        )}
      />

      <Route
        path="/builder-responses/*"
        element={renderShell(
          <BuilderWorkspaceEntry
            workspace="builder-responses"
            user={user}
            initialTab="responses"
            visibleTabIds={["responses"]}
            hideWorkspaceTabs={true}
            lang={lang}
            templateLang={lang}
            appThemeMode={themeMode}
            onAppThemeModeChange={shellProps.onThemeModeChange}
          />,
          { compactSidebar: true }
        )}
      />

      <Route
        path="/builder-data/*"
        element={renderShell(
          <BuilderWorkspaceEntry
            workspace="builder-data"
            user={user}
            initialTab="data"
            visibleTabIds={["data"]}
            hideWorkspaceTabs={true}
            lang={lang}
            templateLang={lang}
            appThemeMode={themeMode}
            onAppThemeModeChange={shellProps.onThemeModeChange}
          />,
          { compactSidebar: true }
        )}
      />


      <Route
        path="/calendar/*"
        element={renderShell(<ReservationCalendarPage user={user} />)}
      />
      <Route
        path="/archive/*"
        element={renderShell(<ArchivePage user={user} />, { compactSidebar: true })}
      />

      <Route
        path="/ecommerce/tags/*"
        element={renderShell(<EcommercePage key="tags" section="tags" user={user} />)}
      />
      <Route
        path="/ecommerce/categories/*"
        element={renderShell(<EcommercePage key="categories" section="categories" user={user} />)}
      />
      <Route
        path="/ecommerce/products/*"
        element={renderShell(<EcommercePage key="products" section="products" user={user} />)}
      />
      <Route
        path="/ecommerce/store/*"
        element={renderShell(<EcommerceStorePage user={user} />)}
      />

      <Route
        path="/my-plan/*"
        element={renderShell(<MyPlanPage lang={lang} user={user} />)}
      />

      <Route
        path="/notifications/*"
        element={renderShell(<NotificationsPage />)}
      />

      <Route
        path="/settings/change-password/*"
        element={renderShell(<ChangePasswordPage lang={lang} />)}
      />

      <Route
        path="/settings/security/*"
        element={renderShell(
          <SettingsPage
            lang={lang}
            user={user}
            onUserUpdated={onUserUpdated}
            initialTab="security"
          />
        )}
      />

      <Route
        path="/settings/*"
        element={renderShell(
          <SettingsPage
            lang={lang}
            user={user}
            onUserUpdated={onUserUpdated}
          />
        )}
      />

      <Route
        path="/admin/users/*"
        element={renderRestrictedPage(appShellContent.restrictedAccess.adminOnly)}
      />

        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </RouteSuspense>
  );
}
