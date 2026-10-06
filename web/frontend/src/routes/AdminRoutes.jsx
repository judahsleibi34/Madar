import { lazy } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import PlatformAdminGate from "../components/DashboardBuilder/PlatformAdminGate";
import { ELearningRouteSkeleton } from "../components/ELearning/ELearningSkeleton";
import RouteSuspense from "../components/common/RouteSuspense";
import { appShellContent } from "../content";
import { DashboardLoadingElement, DashboardShell, RestrictedAccessWindow } from "./shared";

const AdminCommercialPage = lazy(() => import("../components/DashboardBuilder/AdminCommercialPage"));
const Dashboard = lazy(() => import("../components/DashboardBuilder/Dashboard"));
const AdminAccountAccessPage = lazy(() =>
  import("../components/DashboardBuilder/AdminAccountAccessPage")
);
const ELearningWorkspace = lazy(() => import("../components/ELearning/ELearningWorkspace"));
const SettingsPage = lazy(() => import("../components/DashboardBuilder/SettingsPage"));
const UserManagementPage = lazy(() =>
  import("../components/DashboardBuilder/UserManagementPage")
);

function AdminContent({
  lang,
  onGoToDashboard,
  onUserUpdated,
  shellProps,
  themeMode,
  user,
  weeklyScreenTimeSeconds = 0,
}) {
  const location = useLocation();
  const isELearningLoadingPath = location.pathname.startsWith("/e-learning");
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
      fallback={isELearningLoadingPath
        ? renderShell(<ELearningRouteSkeleton pathname={location.pathname} lang={lang} label={lang === "ar" ? "جارٍ التحميل" : "Loading E-learning"} />)
        : <DashboardLoadingElement pathname="/dashboard" lang={lang} />}
      lang={lang}
      variant="dashboard"
    >
      <Routes>
        <Route path="/e-learning/*" element={renderShell(<ELearningWorkspace key={`${user?.tenant_id}:${user?.id}`} user={user} />)} />
        <Route
          path="/dashboard/*"
          element={renderShell(
            <Dashboard
              lang={lang}
              user={user}
              themeMode={themeMode}
              onThemeModeChange={shellProps.onThemeModeChange}
              currentUser={user}
              weeklyScreenTimeSeconds={weeklyScreenTimeSeconds}
            />
          )}
        />

        <Route path="/admin/tenants/:tenantId/commercial" element={renderShell(<AdminCommercialPage currentUser={user} />)} />

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
          element={renderShell(
            <SettingsPage
              lang={lang}
              user={user}
              onUserUpdated={onUserUpdated}
              accountOnly
              accountApiBasePath="/admin/profile"
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

export default function AdminRoutes(props) {
  if (props.user?.account_kind === "platform" && props.user?.user_type === "admin") {
    return <PlatformAdminGate key={props.user.id} user={props.user} onLogout={props.shellProps.onLogout}><AdminContent {...props} /></PlatformAdminGate>;
  }
  return <AdminContent {...props} />;
}
