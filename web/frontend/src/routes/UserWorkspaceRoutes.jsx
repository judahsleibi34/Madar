import { lazy } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";

import RouteSuspense from "../components/common/RouteSuspense";
import EcommerceRouteSkeleton from "../components/DashboardBuilder/EcommerceRouteSkeleton";
import { getBuilderProjectIdFromPath } from "../components/PageBuilder/core/PageBuilder.workspaceRouting";
import { appShellContent } from "../content";
import { DASHBOARD_ROUTES } from "../config/routes";
import { DashboardLoadingElement, DashboardShell, RestrictedAccessWindow } from "./shared";

const ChangePasswordPage = lazy(() => import("../components/DashboardBuilder/ChangePasswordPage"));
const SettingsPage = lazy(() => import("../components/DashboardBuilder/SettingsPage"));
const UserDashboard = lazy(() => import("../components/DashboardBuilder/UserDashboard"));
const MyPlanPage = lazy(() => import("../components/DashboardBuilder/MyPlanPage"));
const NotificationsPage = lazy(() => import("../components/DashboardBuilder/NotificationsPage"));
const loadEcommerceProductEditorPage = () => import("../components/DashboardBuilder/EcommerceProductEditorPage");
const loadEcommercePage = () => import("../components/DashboardBuilder/EcommercePage");
const loadEcommerceDeliveryPage = () => import("../components/DashboardBuilder/EcommerceDeliveryPage");
const loadEcommerceOrdersPage = () => import("../components/DashboardBuilder/EcommerceOrdersPage");
const loadEcommerceLoyaltyPage = () => import("../components/DashboardBuilder/EcommerceLoyaltyPage");
const loadEcommerceThemePage = () => import("../components/DashboardBuilder/EcommerceThemePage");
const loadEcommerceStorePage = () => import("../components/DashboardBuilder/EcommerceStorePage");
const EcommerceProductEditorPage = lazy(loadEcommerceProductEditorPage);
const ArchivePage = lazy(() => import("../components/DashboardBuilder/ArchivePage"));
const EcommercePage = lazy(loadEcommercePage);
const EcommerceDeliveryPage = lazy(loadEcommerceDeliveryPage);
const EcommerceOrdersPage = lazy(loadEcommerceOrdersPage);
const EcommerceLoyaltyPage = lazy(loadEcommerceLoyaltyPage);
const EcommerceThemePage = lazy(loadEcommerceThemePage);
const EcommerceStorePage = lazy(loadEcommerceStorePage);
const CvRerankPage = lazy(() => import("../components/DashboardBuilder/CvRerankPage"));
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
  weeklyScreenTimeSeconds = 0,
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const isBuilderLoadingPath =
    location.pathname.startsWith("/page-builder") ||
    location.pathname.startsWith("/builder-responses") ||
    location.pathname.startsWith("/builder-data") ||
    location.pathname.startsWith("/calendar") ||
    location.pathname.startsWith("/agenda") ||
    location.pathname.startsWith("/archive");
  const isEcommerceLoadingPath = location.pathname.startsWith("/ecommerce");

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
          : isEcommerceLoadingPath
            ? renderShell(<EcommerceRouteSkeleton pathname={location.pathname} lang={lang} label={lang === "ar" ? "\u062c\u0627\u0631\u064d \u0627\u0644\u062a\u062d\u0645\u064a\u0644" : "Loading Online Store"} />)
            : renderShell(<DashboardLoadingElement pathname={location.pathname} lang={lang} />)
      }
      lang={lang}
      variant={isBuilderLoadingPath ? "builder" : "dashboard"}
      delay={isEcommerceLoadingPath ? 0 : undefined}
    >
      <Routes key={`${user?.tenant_id || "unknown"}:${user?.id || "anonymous"}`}>
      <Route
        path="/dashboard/*"
        element={renderShell(
          <UserDashboard
            lang={lang}
            user={user}
            themeMode={themeMode}
            onThemeModeChange={shellProps.onThemeModeChange}
            weeklyScreenTimeSeconds={weeklyScreenTimeSeconds}
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
        element={renderShell(
          <ReservationCalendarPage
            key={`calendar:${user?.tenant_id || ""}:${user?.id || user?.auth_id || ""}`}
            user={user}
            initialView={location.state?.calendarView || ""}
            onViewChange={(nextView) => {
              if (nextView === "agenda") navigate(DASHBOARD_ROUTES.agenda);
            }}
          />
        )}
      />
      <Route
        path={`${DASHBOARD_ROUTES.agenda}/*`}
        element={renderShell(
          <ReservationCalendarPage
            key={`agenda:${user?.tenant_id || ""}:${user?.id || user?.auth_id || ""}`}
            user={user}
            initialView="agenda"
            onViewChange={(nextView) => {
              if (nextView !== "agenda") navigate(DASHBOARD_ROUTES.calendar, { state: { calendarView: nextView } });
            }}
          />
        )}
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
        path="/ecommerce/products/new"
        element={renderShell(<EcommerceProductEditorPage user={user} />)}
      />
      <Route
        path="/ecommerce/products/:productId/edit"
        element={renderShell(<EcommerceProductEditorPage user={user} />)}
      />
      <Route
        path="/ecommerce/delivery/*"
        element={renderShell(<EcommerceDeliveryPage user={user} />)}
      />
      <Route
        path="/ecommerce/orders/*"
        element={renderShell(<EcommerceOrdersPage user={user} />)}
      />
      <Route
        path="/ecommerce/loyalty/*"
        element={renderShell(<EcommerceLoyaltyPage user={user} />)}
      />
      <Route
        path="/ecommerce/theme/*"
        element={renderShell(<EcommerceThemePage user={user} />)}
      />
      <Route
        path="/ecommerce/cv-rerank/*"
        element={renderShell(<CvRerankPage user={user} />)}
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
        element={renderShell(<NotificationsPage user={user} />)}
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
