import { lazy, Suspense } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import ChangePasswordPage from "../components/DashboardBuilder/ChangePasswordPage";
import SettingsPage from "../components/DashboardBuilder/SettingsPage";
import UserDashboard from "../components/DashboardBuilder/UserDashboard";
import MyPlanPage from "../components/DashboardBuilder/MyPlanPage";
import NotificationsPage from "../components/DashboardBuilder/NotificationsPage";
import BuilderFormPreviewPage from "../components/PageBuilder/preview/BuilderFormPreviewPage";
import TenantSiteRuntime from "../components/PageBuilder/runtime/TenantSiteRuntime";
import { appShellContent } from "../content";
import { DashboardLoadingElement, DashboardShell, RestrictedAccessWindow } from "./shared";

const PageBuilder = lazy(() => import("../components/PageBuilder"));

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
    location.pathname.startsWith("/builder-data");

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
    <Suspense
      fallback={
        isBuilderLoadingPath
          ? renderShell(
              <DashboardLoadingElement pathname={location.pathname} lang={lang} />,
              {
                compactSidebar:
                  location.pathname.startsWith("/builder-responses") ||
                  location.pathname.startsWith("/builder-data"),
                isPageBuilderShell: location.pathname.startsWith("/page-builder"),
                lang: location.pathname.startsWith("/page-builder") ? "en" : lang,
              }
            )
          : <DashboardLoadingElement pathname={location.pathname} lang={lang} />
      }
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
        path="/page-builder/form-preview/:formId"
        element={<BuilderFormPreviewPage />}
      />

      <Route
        path="/page-builder/preview"
        element={<TenantSiteRuntime draftPreview />}
      />

      <Route
        path="/page-builder/*"
        element={renderShell(
          <PageBuilder
            key="page-builder-main"
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
          <PageBuilder
            key="builder-responses-page"
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
          <PageBuilder
            key="builder-data-page"
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
    </Suspense>
  );
}
