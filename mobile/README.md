# Madar mobile

This directory is an independent Expo SDK 57 / React Native 0.86 application
using TypeScript and Expo Router. It is not included in the production web
Docker Compose deployment.

The current application is an early navigation/UI prototype with splash,
landing, and placeholder login routes under `src/app/`. It does not yet contain
API integration, authentication, token storage, local persistence, push
notifications, or production deep-link handling. Do not treat the placeholder
login screen or an EAS build as a production-ready authenticated client.

## Local checks

Use Node.js 22.13 or newer, then run:

```bash
npm ci
npm run typecheck
npm run lint
npm run build:web
```

Native release validation still requires reviewed EAS/Android/iOS builds and
device testing. Configure API endpoints and public Expo environment variables
deliberately when that functionality is implemented; never place secrets in
`EXPO_PUBLIC_*` values or commit local environment/signing files.

Follow the versioned Expo SDK 57 documentation referenced in `AGENTS.md` when
changing framework configuration or dependencies.
