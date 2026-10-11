# E-Learning owner UI audit

Inspected before the correction pass on 2026-10-11, schema141.

References: DashboardSidebar/SidebarRow for expandable navigation;
ELearningCoursesPage and AcademyManagementHub for page headers/actions;
ELearningSkeleton, PageHeaderSkeleton and LoadingBar for loading;
commerce tables/status surfaces and elearning-course-form for controls;
PageBuilder inspectors/runtime for authoring and themed public rendering;
ELearningSettingsPage for the existing saved settings contract.

Madar uses Inter with IBM Plex Sans Arabic through --font-family-base, shared
--type-* typography, --space-* spacing, --ui-radius-* corners, --theme-* surfaces
and semantic status colors. Existing ecommerce-page/app-page-intro,
ecommerce-primary/secondary-button, elearning-course-form/status and native
dialog/details patterns are the starting point. Logical inline/block properties
and the global direction/language remain authoritative.

Problems: flat owner navigation; Dashboard renders management and access settings;
Forms list/editor/preview on one screen; response detail below inbox; opportunity
list/editor mixed; application and withdrawal review below lists; financial IDs
presented as primary content; unrelated settings in one programme section;
missing useful loading/empty/retry states; unstyled native controls and deeply
nested cards. Public form renderer uses an admin settings surface, with no Academy
theme integration. Builder's selector has no zero-form CTA or edit navigation.

Correction: independent list/editor/detail routes, bounded contextual form links,
existing capability/configuration driven sidebar groups, overview-only dashboard,
selected-field form inspector and dedicated preview, shared existing token-based
owner layout/control/table treatments and themed public form rendering. Backend,
API contracts, workflow transitions, entitlement authority, schema141 and immutable
migrations remain unchanged. Verification must distinguish native account checks
from isolated browser fixtures rather than grant the test account new privileges.
