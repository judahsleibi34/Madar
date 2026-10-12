# EduHope portable public content

This package seeds the existing Academy Builder, independent E-Learning Forms,
course authoring/media/assessment/certificate services and academy settings.
React reads canonical Madar APIs after import; it imports no EduHope JSON.

`website.json` is the final native-editable, bilingual eleven-page presentation,
exported after actual owner save/preview/publish acceptance. `forms.json` contains
four generic definitions, not submissions. `settings.json` holds tenant values.
`course.json` has ten Levels and89 provisional topics; `teaching.json` contains
ten original demonstration lessons.79 topics remain unpublished outlines.
`assessments.json` contains ten draft Level reviews and five draft65-question CEFR
banks. A62-question draw guarantees at least57 objective/written questions and
2–5 human-graded speaking questions. Passing score70%, five varied attempts.
Official exams/CEFR issuance remain disabled pending educator approval.

`media.json` records the original owner logo and licensed illustrative stock hero
with SHA-256/source/license attribution. Original logo bytes are included.
The importer transfers assets through managed media, downloads only the pinned
licensed photograph when absent, and verifies its hash. Original code-authored
SVG/PNG teaching illustrations are included. Intelligible temporary WAV narration
is generated with `espeak`; it is original provisional teaching material.
No test beeps, private applicant files or learner recordings are included.

## Safe local import

Use the backend virtual environment. The default is a dry-run:

```bash
web/backend/madar_env/bin/python web/scripts/import_eduhope_seed.py --target-tenant 1
```

An explicit initial local application requires `--apply --initialize-existing`,
an authenticated native owner cookie file and the marked isolated144 database.
The importer rejects normal localhost141, production/staging, remote hosts,
wrong tenant/project ownership and unsupported schema. It captures a private
backup before the first mutation. Native owner APIs enforce revision/authorization.
It checkpoints logical-key → actual-ID mappings inside existing Builder seed
metadata after each resource. No additional CMS or schema is introduced.

After reviewing the dry-run:

```bash
web/backend/madar_env/bin/python web/scripts/import_eduhope_seed.py \
  --target-tenant 1 --apply --publish --learning --publish-demo
```

`--publish-demo` explicitly publishes only the ten original demonstration lessons;
it never publishes unfinished official CEFR finals or79 draft outlines.
`--publish` publishes the Builder website. The $30 one-time offering remains draft;
no payment provider, purchase, referral sale or wallet transaction is invented.

Reruns created zero new resources in the actual preview. Forms, settings, course
metadata, website and course authoring hash conflicts stop before mutations.
Owner lesson/question/ordering changes are preserved. After explicitly reviewing
an intended package change, `--reconcile-package` reconciles the website only if
its live owner fingerprint still matches. It cannot erase an owner edit.
`--export-owner-website --apply` explicitly adopts reviewed, saved/published native
presentation into the package; Form/media/course references become logical keys.
`--capture-content-baseline --apply` explicitly adopts reviewed existing course
content for conflict protection. Neither option is an automatic override.

Bootstrap generators in `web/scripts/build_eduhope_*` author provisional public
content only. The website generator writes `website.bootstrap.json`, preserving
the final native schema. Inspect generated changes; do not blindly regenerate
owner-edited content. The importer will reject unsafe reconciliation.

## Persistent editing and recovery

Private configuration and local access files are retained, ignored by Git, under
`web/.eduhope-preview.local/` (directory0700/files0600). They are not seed data.
The database and labelled Docker storage volumes survive application restarts.
The resumable launcher performs no migrations/import/resets:

```bash
web/backend/madar_env/bin/python web/scripts/run_eduhope_preview.py --start
web/backend/madar_env/bin/python web/scripts/verify_eduhope_backup.py --verify
```

The backup verifier captures the marked preview, restores into a NEW marked
disposable database, checks actual table counts/content roots/schema, then removes
only that restore-check database. It never replaces the current editing database.
Managed media persists in the labelled storage volume; filesystem uploads/private
artifacts are retained separately. Preserve both when moving the local workspace.

Preview frontend5180/backend8010/provider55440–55443 are distinct from normal
frontend5173/backend8000/application database141. Emails/push/payouts remain off;
the existing in-app notification worker runs locally on health8098.

## Production destination preparation

`destination.example.json` requires explicit actual tenant mapping and reviewed
ownership/entitlement/schema compatibility evidence. The owner's supplied account
mapping is retained privately. Production tenant/schema are not guessed.
The current importer intentionally authorizes only the local preview. A governed
production-compatible143/144 release, destination verification and explicit import
approval remain required before a remote apply mode can be selected. Git alone
never transfers PostgreSQL rows, auth accounts, responses or customer finances.
Migrations001–143 and excluded142 are unchanged;144 is an unselected candidate.
See `docs/eduhope/local-delivery-report.md` and `requirements.json` for exact
coverage, proof and dependencies.
