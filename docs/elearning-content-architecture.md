# E-Learning course and content architecture

Madar owns generic courses, sections, lessons and ordered lesson content.
Tenant Learning Labels remain presentation-only; routes, tables and navigation
keep normalized names. Settings, course/directory management, Structure,
Learners and Progress retain their existing services and schema gates.

## Lesson content (schema 124)

`elearning_content_blocks` stores `id`, `tenant_id`, `course_id`, `lesson_id`,
`type`, optional `title`, versioned `content`, optional `media_id`, explicit
`position`, author/timestamps and `archived_at`. Section ownership is derived
from the lesson, so moving a lesson cannot leave stale section attachments.
Composite foreign keys enforce tenant/course/lesson and tenant/media ownership.
The type column is a stable string, not an enum or a separate lesson subtype.
Future types extend the validators/editors/renderers and command handler while
retaining the table and generic lesson model.

A lesson may contain any ordered mix of text, audio and video, including only
audio. Lesson descriptions remain metadata. Publication is inherited from the
lesson and its existing course/section eligibility rules; this phase introduces
no separate block publication state, learner delivery or payment processing.
Archived blocks retain content and media and can be restored. Permanent block
deletion requires confirmation and does not delete shared asset files.

| Type | Version 1 payload |
| --- | --- |
| text | `body` (plain text), per-line `formats` (`p`, `h2`, `h3`, `bullet`, `numbered`), inline `ranges` for bold/italic/underline |
| audio | Managed `media_id`; `content.caption` optional |
| video | Managed `media_id`; `content.caption` optional |

Text is a platform-neutral document, never serialized DOM/HTML. Range offsets
use UTF-16 code units, matching browser selections. Backend typed validation
rejects empty text, unsupported formats, invalid offsets, extra fields, arbitrary
URLs and unsupported block types. React text rendering escapes content; the
editor and renderer reuse PageBuilder's existing rich-text range helpers. No
editor dependency is added. Heading/list and inline-format controls operate on
selected lines/text; replacement removes overlapping spans and shifts later spans.

## Authority and ordering

The existing active tenant owner/admin permission authority independently guards
reads, writes and media uploads. Backend routes inject tenant/user identity from
the authenticated session, never from request payloads. Service-role-only RPCs
also check active owner/admin membership for mutations. Direct client table
access and direct service-role content writes are revoked; RLS remains enabled.

`manage_elearning_content` locks the course before the lesson, matching existing
structure/enrollment/deletion commands. It checks `content_revision`, validates
parent relationships and rejects archived courses, sections or lessons. It
validates registered media ownership, status and stored MIME type, locks that
asset, and creates/updates/reorders/duplicates/archives/restores/deletes blocks
in one transaction. Deferred unique positions allow atomic swaps. Active blocks
have contiguous positions; archived blocks occupy the tail. Every mutation also
advances `structure_revision`, invalidating stale course-delete confirmations.
Concurrent edits return a conflict and require reload rather than overwrite.

`get_elearning_content` scopes the entire hierarchy and resolves media metadata
and managed URLs through the registry. Unknown/missing lessons return 404;
pre-123 content reads, writes and uploads fail closed without accessing the new
schema. Other E-Learning features retain their earlier schema gates.

Lesson and section duplication now copy content with fresh block IDs and shared
managed media. Ordinary lesson deletion remains constrained until its blocks
are explicitly removed. Existing confirmed course deletion checks identity,
name and revisions before removing content under the course lock; all deletion
steps roll back if another protected reference blocks deletion. Tenant purge
cascades content; it does not grant ordinary lesson deletion permission.

## Shared media lifecycle

Audio extends Madar's existing managed registry and private `builder-assets`
storage bucket with MP3 and WAV. The existing upload pipeline handles quota
reservations, rate limits, entitlement checks, durable storage, accounting,
audit logging and rollback. Audio uses the shared 50 MB limit; video retains
250 MB. Signature detection, extension/MIME agreement, WAV frame validation and
MP3 frame validation run on the backend. Video retains the existing MP4/WebM
validation policy. Browser recording and external embeds remain future work.

Blocks reference registry IDs, never a separate learning upload store.
Retention lookup includes active and archived content without granting public
visibility. Publishing a lesson/course never makes media public. Existing
managed-asset delivery authorizes private tenant previews, supports byte ranges
and uses the established private/no-store cache behavior and signed storage
fallback. Missing media renders a retry/replacement state. Unattached uploads
retain the existing delayed cleanup policy.

## UI and reusable rendering

Structure's Open Lesson route now hosts the Lesson Builder. Existing dialogs,
forms, notification styles, Learning Labels and global skeletons are reused.
English/Arabic strings, logical spacing, wrapping controls and small-screen
layout support RTL and responsive use. Add Block offers only Text, Audio/Voice
and Video. Each editor saves validated content; page actions reorder, duplicate,
archive and restore. Archived content can be permanently deleted after explicit
confirmation. Private preview uses the same `ContentBlockRenderer` and text/media
renderers as block cards, independently of the management page. These renderers
can serve later learner pages and page-builder integration.

## Release and validation

Migration 124 is an expand-only 123-to-124 transition mirrored between database
and Supabase trees. Earlier SQL/manifests are immutable. The active release
bridges 114..124 with `migrations-115-124.json`; content remains unavailable before
123. Updating protected release metadata requires the governed control-plane
upgrade before any eventual production deployment. Production mutation is not
authorized by this local development task.

Tests cover typed commands, tenant/role isolation, cross-course/lesson/block
protection, media ownership/type/status, shared audio upload validation/rollback,
retention/privacy, ordering, duplication, archive/restore/deletion, parent safety,
transaction rollback, inherited structure/enrollment behavior, labels, loading,
RTL, preview and invalid/error states. SQL tests require an explicitly marked
disposable loopback database; browser verification uses only the local account
and local Docker database.
