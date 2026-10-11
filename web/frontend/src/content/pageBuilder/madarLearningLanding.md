# Madar Learning landing template

`madarLearningLanding.json` remains a Builder-compatible presentation template.
It uses existing Academy course projections and authentication routes; it contains
no copied accounts, courses, or progress records.

Academy rendering and branding always use the API's published Builder schema in
both local development and production. The previous account-specific
`VITE_MADAR_LOCAL_LANDING_PREVIEW` override was removed during the owner UI
correction pass because it masked real Builder publication. The ignored legacy
environment flag no longer changes rendering.

Preview templates through Builder and use its normal revision-checked save and
publish controls. Templates do not select an academy, change entitlements, or
modify registration settings automatically.
