# Immutable release validation

Initial promoted release:

- SHA: `ab6844683d89f652e10edc0bc7fefd22791db75f`.
- Build timestamp: `2026-08-25T16:02:37Z`.
- Backend image ID: `sha256:43ab5b166e74b1a2d67b538ec8a1fb245e791d2889a6cdeec529e5e0f1a7de67`.
- Frontend image ID: `sha256:b693eca7e5074a1e4203fdae00fb2a40dcac02ae661af2944107ab17b217951c`.

Corrective active release:

- SHA: `4faf63a67cbcfe884d3cbeeaa2f39ae9f0a37467`.
- Build timestamp: `2026-08-25T19:14:25Z`.
- Backend image identity:
  `sha256:46223af18eda02603d1c6449d08e3d13b92072605d8ee89f201fbefa916124e2736a4`.
- Frontend image identity:
  `sha256:2cba487320ef895d9377d2dcfd034a440187232d696b7c95a2429f9e3ce4794b`.
- Frontend origin label: canonical production API origin (value intentionally
  non-secret but recorded as policy in source).

Image labels, running bundle and `/health/version` match the release contract.
Release state records active slot green, schema 83, no in-progress release,
and zero failed releases.

The preincident `0eaa9edd...` images retain explicit rollback tags for forensic/recovery purposes, but schema-83 rollback authority is the retained compatible blue `ab684468...` slot. Old code is not treated as safe against a schema it never declared compatible with.
