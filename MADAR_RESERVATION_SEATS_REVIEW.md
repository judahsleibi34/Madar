# Reservation session seats — local review

2026-11-02. Owner checkout, Judah_branch. No commit, deployment, persistent migration or release selection.

## Behavior

- Each fixed appointment/time can be one-to-one (one person) or a group (2–1000 people). Click its summary to edit its own type and people limit.
- Dates organize appointments; they do not own a shared session type or people limit. Mixed one-to-one and group appointments can appear on the same day.
- Per-appointment settings are saved by date/time in `sessionSettingsByDate`. Renaming a time moves its settings; removing it prunes them. Weekly appointments inherit settings from their exact source appointment; explicit dates keep their own settings.
- Visitors to a group session can request multiple seats. The API validates whole seat quantities against the authoritative published block. Private sessions accept one seat; date requests keep their existing behavior.
- New appointments default to one-to-one. Previously saved block-wide settings remain a compatibility fallback until each appointment is edited; existing data is not silently reset.
- The editor uses the existing flat light application theme.

## Database candidate and installed behavior

`web/database/candidates/reservation_seat_capacity.sql` is an unselected review candidate, outside the migration directories. It does not update schema state, replace published functions, modify migration checksums or select a release.

Group requests call a dedicated service-only wrapper around the retained notified reservation RPC. Each booking snapshots its selected appointment settings separately from the complete block configuration. The candidate trigger uses that resolved snapshot, counts people, serializes the retained per-block advisory lock, preserves private exclusivity, and checks active inserts/reactivations. Cancellation frees seats; retries do not reserve twice. Notification failure rolls back the seat. Non-read-committed transactions refuse rather than counting a stale snapshot.

**Group booking is not active on the installed database.** If the new adapter is absent, the API refuses explicitly with `reservation_capacity_unavailable`; it never falls back to unlimited inserts or disables the existing exclusive-slot protection. The visitor receives a contact-organizer message.

Mixed historical capacities are conservative: the smallest overlapping recorded capacity applies, and an existing private reservation retains one-seat exclusivity. Raising a block's limit does not silently relax existing sessions' recorded limits. No historical reservations are rewritten. A reviewed policy for changing the capacity of an already-booked session remains a release gate.

## Verified local evidence

Private, Git-ignored evidence is retained in `private-evidence/reservation-seats/`:

| Check | Result | Evidence |
| --- | --- | --- |
| Editor, booking form, weekly-date, component-builder and submission tests | 31 passed | frontend-tests.log |
| Seat validation, configured-date validation, retained release contract | 15 passed | backend-tests.log |
| Native PostgreSQL 17.11 | 9 passed | postgres.log |
| Local Chromium, synthetic mounted editor | 390/760/1024/1280/1680px; mixed appointments, capacity edit, time rename, other-day isolation, no overflow; flat light theme | individual-browser.log, individual-sessions.png, individual-editor-*.png |
| Frontend build, theme and tenant-bundle audits | Passed | build.log |
| Targeted ESLint and git diff --check | Passed | local commands |

Native tests also prove that a selected appointment snapshot overrides a different block default, so mixed-session limits are independent. Native tests cover weighted seats, a contended final-seat race, idempotent replay, cancellation/replacement/full reactivation refusal, direct reactivation refusal, private slots, independent blocks/times, wrong-tenant refusal, invalid quantities, repeatable-read refusal, service-only access and notification rollback.

The native fixture uses the real retained create/notified/status SQL in an isolated, network-disabled PostgreSQL container. Its ownership tables are synthetic and its notification-intent sink is a fixture. It does not prove complete PostgREST integration, real notification delivery, account-lifecycle fencing or production readiness. The browser evidence is an isolated mounted component, not a live authenticated tenant test. The UI shows the configured seat limit, not a live remaining-seat counter; the database remains authoritative on submission.

## Remaining gates

1. Independently review and integrate the SQL through the authorized release lineage, compatibility checks and migration checksums, including the existing unselected candidates. Preserve active schema146 and candidate167 selection status until separately authorized.
2. Establish the intended policy for editing capacity on already-booked sessions; prove no silent cancellation, overbooking or loss of existing reservations.
3. Rehearse the complete candidate schema via real PostgREST, published-site APIs, tenant/member authorization, status/cancellation RPCs, notification outbox and applicable account-lifecycle fences. Prove old/new binary behavior and reactivation concurrency under that exact lineage.
4. Review the UI and operational acceptance evidence before any separately authorized installation or release activation. No such operation was performed here.

Published migration and release metadata paths have no changes from this work. Owner work and recovery stashes were not altered. Disposable test services were stopped after verification.

## Booking-form editor follow-up

The form editor now follows the Page Builder workspace: a form chooser and Save action above the editor; Add fields / Field order on the left; a clean form preview in the middle; and selected-field settings on the right. The duplicate booking-list sidebar is hidden during form editing. The chooser retains access to other forms and creation actions. Appointment availability remains in its existing view.

Sorting uses saved field IDs and preserves field settings. Users can drag dedicated handles in the preview/order list, use up/down buttons, or press Alt+Up/Down on a focused field. Before/after drop positions support moving to the first or final field. Application heading styles no longer override authored text sizes in this form preview.

Validation: 11 focused form/editor tests; native Chromium drag to first and final positions, keyboard movement, adding a field, authored 22px preview text, and responsive layout at 390/760/1024/1280/1680/1920/5760 CSS pixels; theme audit and targeted ESLint pass. Evidence: `private-evidence/reservation-seats/form-builder-layout.log`, `form-field-order.png` and `form-builder-*.png`. Preview Vite stopped after verification.

### Panel sizing and scrolling correction

Owner identified panel sizes/scrolling as the priority. Desktop form editing now fits the parent workspace height, keeps its Save/header outside the scrolling panels, and gives tools, preview and settings independent scrolling. Redundant introductory space/footer is hidden while editing. The form page is capped at 760px within the preview; tools/settings remain 240px/300px. Field tabs and settings heading stay visible during panel scrolling. Smaller screens retain the stacked page-scroll layout.

Native browser acceptance proves that all panel bottoms stay within the viewport; the main workspace does not scroll; each panel independently accepts a nonzero scroll offset; Save stays visible even at 1280×640 with 140px reserved for app chrome. Native field drag/keyboard sorting still passes. Eleven focused tests, theme audit, ESLint and diff checks pass. Evidence: `private-evidence/reservation-seats/bounded-form-builder.log`, `bounded-short-screen.png`, `bounded-form-builder-*.png`. Temporary preview stopped.

### Full-width preview and translations

The owner's subsequent preference replaces the earlier 760px preview cap: the form now fills the centre panel's available content width, with standard workspace padding. Independent scrolling and the fixed side panels remain.

The booking editor uses the application's `pageBuilder` translation namespace for English/Arabic. Coverage includes management controls, field names, inspector/formatting controls, sort actions, appointment controls, weekly repetition, calendar labels and localized dates. Arabic mirrors the editor panels and uses RTL layout. Existing authored names, questions, options and instructions are preserved when the interface language changes. Newly created fields/forms use localized defaults and content direction; Arabic text defaults use IBM Plex Sans Arabic. Shared builder navigation/helper text and history controls also have Arabic copy.

Verification: all English editor messages have Arabic entries; 20 focused editor/i18n/navigation tests pass; targeted ESLint, theme audit, build and tenant-bundle audit pass. Local Chromium checks full-width preview across seven widths, independent scrolling, native sorting, language switching, RTL panels, localized new fields and calendar controls. Evidence: `private-evidence/reservation-seats/full-width-translations.log`, `translation-tests.log`, `build.log`, `full-width-form-*.png`, `full-width-arabic.png`. Temporary preview stopped; no persistent database or release operation.

### Authored form translations

The owner's clarification concerns form content as well as interface labels. Select a field, open **Translations** in its settings, and choose English or العربية. Headings/instructions, labels, placeholders, choice labels and submit-button text now support independently entered translations. Empty boxes fall back to the original wording. The **Preview language** control above the canvas switches the form preview; it does not change the application's interface language. Translations travel with each field through the existing project Save flow. Text is entered by the author; this feature does not generate automatic translations.

Rendering uses the visitor's existing site language. Arabic translated text uses RTL direction and Arabic typography. Choice labels are translated separately from canonical option values, so existing saved answers and backend validation retain their original values. Normalization bounds translation text and accepts only supported languages/current options.

Verification: 32 focused form/editor/i18n tests pass, including JSON serialization/reload, blank-language fallback, editing translations without rewriting original text, and an Arabic runtime submission retaining the canonical choice value. Local Chromium verifies the field-settings access path, live Arabic preview, English fallback, synthetic local serialization/reload and translated choice labels. This browser fixture does not certify authenticated project persistence or production deployment. Targeted ESLint, build, theme and tenant-bundle audits pass. Evidence is retained privately in `private-evidence/reservation-seats/content-translations-tests.log`, `content-translations-build.log`, `content-translations-browser.log`, `content-translations-arabic.png` and `content-translations-fixture.mjs`. No database, migration selection or release activation changed.


## Responsive booking component layout

Booking forms now expose Desktop, Tablet and Mobile views above the canvas,
using the existing builder device names and preview widths. Select a component
and use Size and position in its inspector to set width, row placement, minimum
height, and space above/below. The selected component also has an edge resize
handle with pointer and keyboard support; Field order and existing drag handles
continue to change component order without losing translations or device layout.
A continuous pointer resize creates one undo entry. Direct heading/paragraph
editing remains available.

Layouts use a bounded 12-column flowing grid with intrinsic content height.
Tablet inherits desktop until overridden; mobile defaults to full width until
explicitly customized. Reset this view removes only the current device override.
Visitor forms use their available container width (mobile through 600px, tablet
through 1024px), while editor device selection explicitly previews that layout.
Width and spacing are sanitized and preserved through form normalization and
JSON serialization. EN/AR inspector controls are included. Existing forms keep
their full-width flow. This adds no absolute positioning or overlapping layers.

Verification: 31 focused tests passed, targeted ESLint passed, and the frontend
build and included theme/bundle/tenant audits passed. Chromium synthetic fixtures
verified desktop width/placement, pointer resizing, separate mobile defaults,
local serialization/reload, inline editing, side-by-side runtime fields at
1200/768px, stacked fields at 390px, custom mobile width/end alignment/minimum
height/spacing, and ordering with layouts intact. No browser errors or horizontal
runtime overflow were observed. Screenshots were inspected. These fixtures do
not verify an authenticated project save or a production release.

Durable private evidence: `private-evidence/reservation-seats/responsive-layout-`
files (tests/build/browser logs, reproducible synthetic fixture and editor/runtime
screenshots). No database, migration selection, deployment or release activation
changed.


## Horizontal component movement

Selected components now expose a horizontal move handle above their boundary,
separate from the existing resize and reorder handles. Pointer dragging and
left/right arrow keys move the component across the row, snapping to the same
12-column responsive grid. The inspector also exposes Horizontal position.
Full-width components show guidance to reduce width before moving; movement is
bounded to the row. Custom start columns are sanitized against component width,
serialized with each device layout, and applied by both preview and visitor
renderers. Mobile defaults, translations, field IDs and ordering are preserved.
Horizontal movement does not clone components. A pointer gesture uses one undo
entry. Width changes clamp custom positions to valid bounds during normalization.

Verification: 16 focused layout/editor/i18n tests and targeted ESLint passed.
Native Chromium synthetic fixtures verified horizontal pointer drag, arrow-key
movement, unchanged component count/identity, independent device settings,
serialization/reload, resize and ordering regressions, and visitor layouts at
1200/768/390px without horizontal overflow or browser errors. Evidence is in
private `horizontal-position-*` logs, fixture and screenshots alongside the
previous responsive-layout evidence. This does not exercise authenticated
backend project saving or grant deployment authority.

The frontend build and included bundle/theme/tenant audits also passed for this change.


## Simplified component inspector

Removed the Size and position inspector panel at owner request. Canvas resize, horizontal move and reorder handles remain, with existing responsive layout data preserved. The Translations disclosure now uses a compact 20px text line and 6px vertical padding, with no minimum card height or shadow. This supersedes earlier instructions to use inspector width/position/spacing controls.


## Builder selection handle alignment

Booking components now reuse the page builder direct-move-handle and direct-resize-handle classes and the same 13px four-direction Move icon. Controls sit at the top-left and bottom-right of the selected boundary. Removed the extra canvas grip; drag sorting remains in Field order and Alt+Up/Down remains supported. Unselected handles stay hidden, including disabled full-width handles. Existing horizontal movement and width-resize behavior is preserved. Nine focused builder tests, targeted ESLint and a Chromium visual check passed. Private builder-handles evidence records shared classes, dimensions/colors, hidden unselected handles and keyboard movement. A full build was not rerun for this control presentation change.


## Vertical movement on the shared move handle

The builder-style Move handle now accepts both pointer axes. Vertical movement
adjusts the selected device's space above the component, keeping intrinsic form
flow and moving later rows to prevent overlap. Up/down arrow keys adjust this
spacing by 10px; horizontal movement remains grid-snapped. Full-width components
can now use the move handle vertically. Upward motion stops at the component's
flow position (zero added spacing); changing field order remains available in
Field order or with Alt+Up/Down. This is flow-preserving placement, not arbitrary
absolute positioning across other fields. Vertical spacing is bounded to
0–10000px, persisted by normalization and applied by the existing visitor layout.

Verification: 17 focused layout/editor/i18n tests and targeted ESLint passed.
Chromium verified an 80px downward drag, a 30px upward drag, unchanged width,
independent mobile placement, serialization/reload and visitor rendering of the
resulting 50px spacing, without browser errors. Frontend build and included
bundle/theme/tenant audits passed. Durable private evidence uses vertical-drag-*
files. Synthetic browser persistence does not verify authenticated backend save.


## English heading synchronization

Heading text is now the canonical English heading. The English translation input loads its actual value immediately; editing either input or the English canvas heading updates both stored values. Arabic remains independent. Form normalization reconciles stale English heading overrides with Heading text, and English rendering preserves the heading’s authored typography/direction. Verified by 32 focused editor/form/runtime tests and targeted ESLint. Durable test output: private-evidence/reservation-seats/heading-english-sync-tests.log. No browser fixture or full build was rerun for this focused synchronization change.


## Canvas drag ordering (supersedes vertical spacing drag)

The Move handle now reorders components when dragged vertically across other
components. A temporary moving preview and insertion line show the destination;
releasing places the original component before/after the target without adding
spacing. Horizontal placement is committed on release, alongside any reorder.
The pointer preview leaves saved component data untouched until release, and
Escape/pointer cancellation discards it. Canvas edges auto-scroll during a drag.
Up/down keys on the Move handle now reorder fields. This replaces the prior
vertical behavior that only adjusted spaceAbove and could not cross other fields.
Existing authored layout and translations are preserved; IDs and component count
do not change. Saved order is shared across device views, like Field order.

Verification: 15 focused editor/i18n tests, targeted ESLint, frontend build and
included bundle/theme/tenant audits passed. Chromium exercised the exact case
Reserve now below New header, then back above it; insertion indication; preserved
Arabic text/width; unchanged component count; no added spacing; reload and visitor
order; Escape cancellation; and automatic scrolling to a lower drop target. No
browser errors were observed. Private durable evidence: canvas-reorder-* logs,
fixture and screenshot. Browser persistence uses synthetic local serialization,
not an authenticated backend project save.


## Compact component boundaries and removal of spacer artifacts

Removed hidden native-drop strips from normal layout; they are now temporary
absolute overlays during native drags. Pointer insertion lines already overlay
the canvas. Component preview padding and default text margins no longer inflate
selection boundaries. Grid rows pack at intrinsic height instead of stretching,
and the form page no longer enforces a 360px minimum height. The normal inter-row
gap remains 16px. Previously stored minHeight/spaceAbove/spaceBelow metadata is
preserved in project data but no longer emitted into the rendered layout, so old
spacing-only drag artifacts cannot create gaps in either editor or visitor form.
Widths, horizontal placement, order, text and translations remain intact. This
supersedes earlier descriptions of applying vertical spacing metadata.

Verification: 28 focused builder/layout/visitor tests, targeted ESLint, frontend
build and included audits passed. Chromium used a fixture with 120px above,
80px below and a 400px minimum height saved on a heading; confirmed none inflated
the editor or visitor form, hidden drop zones occupied no height, preview padding
was zero, component height was natural, and row gap was at most 18px including
selection borders. The drag-below/above-heading, cancellation, reload, visitor
order, preserved metadata and auto-scroll checks also passed. Screenshot inspected.
Private durable evidence: compact-canvas-* files. Fixture persistence is local
serialization, not authenticated backend saving.


## Divider component

Added Divider / فاصل to booking Add fields. It uses the shared theme border color, a horizontal separator role, a compact selection target and the existing responsive width, move, reorder and removal controls. Multiple dividers are permitted and survive normalization/serialization. They do not expose text/translation/direction settings or create required answers. Both editor and visitor form render them. Verified the combined 34-test focused suite, then the updated 15-test visitor file including divider position/width; targeted ESLint and frontend build with included audits passed. Durable private logs: divider-tests.log, divider-runtime-tests.log and divider-build.log. No browser fixture was run for this addition.


## Visible control resizing

The submit button now fills its authored component width rather than keeping an
independent intrinsic width. Corner resizing handles both axes; text inputs also
follow explicit resized height. New contentHeight metadata (32–2000px) records
intentional control resizing per device, separately from obsolete minHeight and
spaceAbove/spaceBelow metadata, which remains ignored. Tablet inherits desktop;
mobile retains its own default or override. Up/down keys on the resize handle
adjust height; the move handle continues to reorder. English/Arabic heading sync
and compact intrinsic rows remain unchanged.

Verification: 32 focused builder/layout/visitor tests, targeted ESLint, frontend
build and included audits passed. Native Chromium measured visible button width
and height before/after a corner drag and confirmed its width matches the frame.
It also measured both input axes, independent mobile height, reload and visitor
button/input dimensions. No browser errors. Screenshot inspected. Durable private
evidence: control-resize-* files. Browser persistence uses local fixture JSON,
not an authenticated project save.


## RTL mirroring

Arabic preview and visitor language now set the form grid's direction, mirroring
logical column placement, field flow and controls independently of editor UI
language. Arabic fallback content receives RTL alignment even before translation
text is entered. Each component's direction toggle consistently controls its
contents and selection handles; Arabic direction overrides persist separately
from English. English heading text remains canonical and unchanged by language
switching. Move/resize handles mirror to the top-right/bottom-left for RTL;
movement uses canvas direction and resize uses the component's active edge.
When component and canvas directions differ, resizing preserves the opposite
edge. Choice controls, list indentation and calendar chevrons mirror as well.
The normal booking calendar also receives the visitor direction. Switching to
LTR restores LTR flow; Arabic editor UI mirrors the toolbox/inspector panels.

Verification: 39 focused builder/i18n/form/visitor tests, targeted ESLint,
frontend build and included audits passed. Native Chromium verified field column
mirroring/restoration, handle positions, RTL resize direction/anchor, physical
arrow-key movement, per-component override in an opposite-direction canvas,
heading alignment, choice placement, list indentation, direction persistence,
unchanged English text, visitor column order, calendar chevrons and Arabic editor
panel positions. No browser errors. Screenshot inspected. Durable private evidence:
rtl-mirror-* files. Synthetic local serialization does not verify authenticated
backend project saving.


## Fixed component translations

Replaced the Arabic reservation-content alias to English with real Arabic
content. Built-in booking headings/sections, fixed name/email/phone fields,
submit and seat labels, calendar navigation/availability/time accessibility
labels, empty states, phone helpers and client validation messages follow the
visitor language. Defaults localize when not authored explicitly; authored text
and canonical service/answer values remain unchanged. Builder preview helpers
follow Preview language rather than the editor UI language. Regional Arabic
locale identifiers resolve to Arabic content. English content remains available.

Verification: 44 focused content-parity, builder/i18n, form-validation and visitor
tests, targeted ESLint, frontend build and included audits passed. Chromium
checked Arabic fixed field/calendar/seat/time/submit labels, required validation,
flexible section headings, empty slot state, English restoration and Arabic
preview helper text without browser errors. Screenshot inspected. Private durable
evidence: fixed-translations-* files. Fixture browser persistence is synthetic;
no authenticated backend saving, release activation or database change occurred.


## Starter content inside composed forms

Arabic preview and visitor rendering now translate recognized English starter
headings, template instructions, availability/question/email/phone labels,
question placeholders, submit labels and default choice labels inside existing
saved component arrays. This covers both request and fixed-slot templates.
Automatic lookup is restricted by component type and field to exact known
starter copy; custom text is left intact and explicit Arabic translations take
precedence. Choice values remain canonical. The Arabic inspector inputs display
the same automatic text and accept authored overrides. English heading sync is
unchanged. Source component data is not rewritten by language switching.

Verification: 47 focused content/editor/form/visitor tests, targeted ESLint,
frontend build and included audits passed. Chromium recreated the screenshot's
instructions, email label, new heading, question/placeholder and Send request;
confirmed Arabic inside the canvas and visitor form, populated Arabic editing
fields, authored override persistence, unchanged English source/custom heading,
canonical default choice values, reload and English restoration. No browser
errors. Screenshot inspected. Durable private evidence: starter-translations-*
files. Browser persistence remains synthetic local JSON, not authenticated save.


## Inspector scroll overlap

Removed sticky positioning from the field settings heading; it now scrolls with its controls instead of covering the formatting toolbar. Toolbox tabs retain their existing sticky behavior. Chromium verified a 600px-high viewport in English/Arabic preview, title scrolling out of view, formatting controls receiving pointer hit tests, and editing after scroll without browser errors. Screenshots inspected; git diff whitespace check passed. Private durable evidence: inspector-scroll-* files. Full build/unit suites were not rerun for this focused CSS correction.


## Formatting panel theme sizing

Formatting controls now use global small/caption typography and regular font weight, compact control-height tokens and proportional icons. Numeric fields use a compact inset height; button/select sizes scale with the theme font instead of inheriting oversized general form dimensions. Authored text font sizes remain editable independently. Chromium measured 14px controls, 12px captions, 36px buttons/selects, 28px numeric fields and 14px icons; increasing the theme font to 16px produced 40px controls/16px icons without horizontal overflow. Editing the authored font-size field still worked. Screenshot inspected; diff whitespace check passed. Durable private evidence: toolbar-theme-* files. Full build/unit suites were not rerun for this scoped CSS change.


## Toolbox overlap and removal of Field order

Removed the separate Field order view, its tab/state/order-list controls and unused icons/styles. Add fields is a plain localized heading that scrolls with the palette; the sticky tab overlay no longer covers component cards. Canvas pointer ordering, move-handle keys and Alt+Up/Down remain available. Nineteen focused builder/i18n tests, targeted ESLint, frontend build and included audits passed. Chromium verified palette scrolling/card pointer access at a 600px viewport height, adding after scrolling, Arabic heading and absence of tabs. The native canvas reorder/reload/visitor/cancel/auto-scroll fixture also passed again. Private durable evidence: toolbox-simplify-* and refreshed canvas-reorder-browser.log. Screenshots inspected.


## Back to reservations navigation

Added a localized Back to reservations button before the form selector in the editor header. It returns scheduled forms to availability and date-request forms to a non-editor reservations overview with the booking list and Builder entry visible. Current form edits remain in parent state, and reopening the builder restores them. Navigation does not invoke Save or modify booking data. The Arabic button uses the mirrored chevron. Fifteen focused reservation-navigation/i18n tests, targeted ESLint, frontend build and included audits passed. Chromium verified top placement, both booking types, visible overview/list or availability, edit preservation on reopening, no automatic save and Arabic return navigation. Screenshot inspected; no browser errors. Durable private evidence: back-reservations-* files. Synthetic local state does not verify authenticated backend persistence.


## Reservation flow header isolation

The shared workspace header now suppresses the entire Pages / Header & Footer / Publish subbar when activeTab is reservations, for both overview and form editing. Undo/Redo move into the project topbar using existing history-control styling. Design, chrome and publish retain their navigation. Thirteen focused header/subbar/reservation tests, targeted ESLint, frontend build and included audits passed. Chromium combined the actual shared header and ReservationsTab to verify no navigation/subbar before or after Back, retained header history controls, both booking modes, preserved edits/reopening and Arabic return navigation. Screenshot inspected; no browser errors. Private durable evidence: reservation-flow-header-* files. No authenticated backend save or deployment occurred.
