# Publication snapshot consistency

Public bootstrap data now derives branding, logo, header, footer and loading configuration from the same bound `published_schema.siteChrome` snapshot used for body content. It no longer combines published body content with mutable current/draft `website_settings`. The publication identity participates in the returned metadata/ETag path.

Regression coverage checks snapshot branding and public schema behavior. Public asset authorization also verifies tenant/project publication references. No styling, component layout or brand design changed.

Promotion validation must publish two deliberately different snapshots in staging, bind only one, and prove body/chrome/logo/header/footer/loading and ETag all remain on the bound identity through cache hit, republish and rollback scenarios.
