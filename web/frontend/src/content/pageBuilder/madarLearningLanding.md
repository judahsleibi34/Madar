# Madar Learning landing template

`madarLearningLanding.json` is a Builder-compatible presentation for the local
`testing` academy. It uses existing Academy course projections and authentication
routes; it contains no copied accounts, courses, or progress records.

To preview it with the frontend development server, set
`VITE_MADAR_LOCAL_LANDING_PREVIEW=true` in `.env.development.local`. This preview
applies only in development and only to `/academy/testing`; production continues
to render the tenant's published Builder schema. The local preview flag is
currently enabled in the ignored environment file.

Builder publication must use the normal revision-checked save/publish APIs once
the local workspace has valid commercial access. The previous local landing and
settings were backed up to `/tmp/madar-learning-settings-backup.json`. Publication
was rejected with `commercial_access_expired`; no Builder records were changed.

Log in and Sign up use `/academy/testing/login` and its `register=1` mode. Successful
authentication continues to `/academy/testing/dashboard`. Email verification
remains required when the registration API requests it. The isolated local
academy now allows open registration, and automatic test login is disabled so
the real forms can be exercised.
