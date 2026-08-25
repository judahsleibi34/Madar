# Immutable release validation

Active release:

- SHA: `ab6844683d89f652e10edc0bc7fefd22791db75f`.
- Build timestamp: `2026-08-25T16:02:37Z`.
- Backend image ID: `sha256:43ab5b166e74b1a2d67b538ec8a1fb245e791d2889a6cdeec529e5e0f1a7de67`.
- Frontend image ID: `sha256:b693eca7e5074a1e4203fdae00fb2a40dcac02ae661af2944107ab17b217951c`.

Image labels and `/health/version` match the SHA/build timestamp. Release state records active slot blue, schema 83, no in-progress release, and zero failed releases.

The preincident `0eaa9edd...` images retain explicit rollback tags for forensic/recovery purposes, but schema-83 rollback authority is the compatible green `ab684468...` slot. Old code is not treated as safe against a schema it never declared compatible with.
