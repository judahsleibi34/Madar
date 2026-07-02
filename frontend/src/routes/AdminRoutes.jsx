import { Navigate, Route, Routes } from "react-router-dom";

import Dashboard from "../components/DashboardBuilder/Dashboard";
import AdminAccountAccessPage from "../components/DashboardBuilder/AdminAccountAccessPage";
import NotificationsPage from "../components/DashboardBuilder/NotificationsPage";
import UserManagementPage from "../components/DashboardBuilder/UserManagementPage";
import { appShellContent } from "../content";
import { DashboardShell, RestrictedAccessWindow } from "./shared";

export default function AdminRoutes({
  lang,
  onGoToDashboard,
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
        path="/my-plan/*"
        element={renderRestrictedPage(
          appShellContent.restrictedAccess.workspaceOnly
        )}
      />

      <Route
        path="/settings/*"
        element={renderRestrictedPage(
          appShellContent.restrictedAccess.workspaceOnly
        )}
      />

      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
