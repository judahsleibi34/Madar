# Superseded architecture history — not an upgrade path

These exact SQL bytes were published on PR220 before main independently assigned
147–156 to data-source functionality. They are retained for forensic comparison
and disposable historical regression fixtures, outside the active migration tree.
Their original mirrors are under `web/supabase/historical-architecture-146-150`.

Canonical databases follow main through156, then new157–160. Never apply these
files to a canonical database, infer history from a schema number alone, or
reinterpret the old146→150 contracts as146→160 authority. A persistent database
that applied this divergent history needs a separately reviewed recovery/forward
plan. Original manifests retain their historical bytes; execution is refused.
