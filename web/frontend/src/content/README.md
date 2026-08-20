# Content System

Website text lives in `src/content`.

- `siteContent.js`, `navigationContent.js`, and `footerContent.js` hold shared brand, navigation, and footer copy.
- `pages/*Content.js` holds page-specific sections such as hero copy, cards, form text, and CTA labels.
- `components/*Content.js` holds copy for reusable UI pieces such as modals and forms.

Use the exported `get...Content(lang)` helpers in React components, or import the named content object when a component does not need runtime language selection.

The structure mirrors a future `src/i18n/en`, `src/i18n/ar`, or `src/i18n/he` split: each module keeps language-specific content under `en` and `ar`, with nested keys such as `hero.title`, `form.success`, or `sections.items`.

When adding a new public page, create a file in `src/content/pages`, export it from `src/content/index.js`, and pass the content into page blocks/components instead of hardcoding text in JSX.
