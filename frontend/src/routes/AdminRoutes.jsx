import { lazy } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import RouteSuspense from "../components/common/RouteSuspense";
import { appShellContent } from "../content";
import { DashboardLoadingElement, DashboardShell, RestrictedAccessWindow } from "./shared";

const Dashboard = lazy(() => import("../components/DashboardBuilder/Dashboard"));
const AdminAccountAccessPage = lazy(() =>
  import("../components/DashboardBuilder/AdminAccountAccessPage")
);
const SettingsPage = lazy(() => import("../components/DashboardBuilder/SettingsPage"));
const SecurityMfaPage = lazy(() => import("../components/DashboardBuilder/SecurityMfaPage"));
const NotificationsPage = lazy(() =>
  import("../components/DashboardBuilder/NotificationsPage")
);
const UserManagementPage = lazy(() =>
  import("../components/DashboardBuilder/UserManagementPage")
);

export default function AdminRoutes({
  lang,
  onGoToDashboard,
  onUserUpdated,
  shellProps,
  themeMode,
  user,
}) {
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
      fallback={<DashboardLoadingElement pathname="/dashboard" lang={lang} />}
      lang={lang}
      variant="dashboard"
    >
      <Routes>
        <Route
          path="/dashboard/*"
          element={renderShell(
            <Dashboard
              lang={lang}
              user={user}
              themeMode={themeMode}
              onThemeModeChange={shellProps.onThemeModeChange}
            />
          )}
        />

        <Route
          path="/admin/users/*"
          element={renderShell(
            <UserManagementPage lang={lang} currentUser={user} />
          )}
        />

        <Route
          path="/admin/account-access/*"
          element={renderShell(
            <AdminAccountAccessPage
              lang={lang}
              themeMode={themeMode}
              currentUser={user}
            />
          )}
        />

        <Route
          path="/notifications/*"
          element={renderShell(<NotificationsPage />)}
        />

        <Route
          path="/page-builder/*"
          element={renderRestrictedPage(
            appShellContent.restrictedAccess.workspaceOnly
          )}
        />

        <Route
          path="/builder-responses/*"
          element={renderRestrictedPage(
            appShellContent.restrictedAccess.workspaceOnly
          )}
        />

        <Route
          path="/builder-data/*"
          element={renderRestrictedPage(
            appShellContent.restrictedAccess.workspaceOnly
          )}
        />

        <Route
          path="/archive/*"
          element={renderRestrictedPage(
            appShellContent.restrictedAccess.workspaceOnly
          )}
        />

        <Route
          path="/my-plan/*"
          element={renderRestrictedPage(
            appShellContent.restrictedAccess.workspaceOnly
          )}
        />

        <Route
          path="/settings/security/*"
          element={renderShell(<SecurityMfaPage lang={lang} />)}
        />

        <Route
          path="/settings/*"
          element={renderShell(
            <SettingsPage
              lang={lang}
              user={user}
              onUserUpdated={onUserUpdated}
              accountOnly
              accountApiBasePath="/admin/profile"
            />
          )}
        />

        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </RouteSuspense>
  );
}
