# Retirement-to-staging failure diagnosis

The consumed plan 8d2813a475e13640b56d1215e92b30ebd34e058b879f862ef2446b9940c9eef1
failed at 16:09:33.974849 UTC after stopping the bound unpublished frontend,
backend and parser, before candidate-contract creation. Its frozen journal
contains RuntimeError only; its actual error message/stack was not retained.
Docker event history for that interval is no longer available. Original records,
resources, checkpoint, authorizations and the public restricted route remain.

The remaining frozen path is: final prior-candidate identity verification,
require_unreserved_ports, retained Redis inspection/guard, then candidate-contract
creation. RuntimeError can arise in those identity checks, the socket/reservation
probe, command wrappers or Redis guard. Subsequent read-only checks cannot identify
which historical raise fired; the historical exact exception is UNVERIFIED.

## Demonstrated mechanism

A real disposable HTTP container published an unused loopback port. Its response
closed the connection; after Docker stop the container was exited, no LISTEN
socket existed, but a server-side TIME_WAIT socket remained. The frozen
require_unreserved_ports raised detached_port_unavailable_<port>_errno_98.
An exclusive SO_REUSEADDR bind+listen passed and a real replacement Docker
container started on that same port. The original independent reproduction
record is preserved in the development checkout's incident-response directory.
This demonstrates a concrete staging false rejection in the precise post-
retirement check; it does not recover the historical exception message.

The minimal correction matches Docker's listener semantics: SO_REUSEADDR, then
exclusive bind+listen, never SO_REUSEPORT. Actual live owners still reject;
unknown/changed Docker reservations, container identities and specifications
remain forbidden. Preflight and post-retirement staging call the same checker.

Real full-sequence tests call the actual production retirement and stage methods
with exclusively disposable containers/networks/volumes, ephemeral ports and
fixture lock files. Authority/configuration and the native client network are
explicit synthetic dependency seams: no protected production receipt or customer
DB is used. Real backend/frontend/parser resources and three CREATED workers,
role aliases, actual network object IDs, names, specifications and loopback
bindings are verified. A distinct fixture fallback remains HTTP200 through
retirement, replacement and injected interruption. These tests are engineering
proof, not application acceptance or production authorization.

New protected diagnostics retain operation, phase, exception type, useful
source-relative function/line frames and OS errno. They exclude exception
messages, source lines, locals, private paths, commands and configuration/customer
values. Diagnostics append to the existing plan-bound journal; old evidence is
never rewritten and a failed operation cannot replay its authorization.

The final cutover proposal must separately bind accepted exact-source images,
actual independent acceptance, the existing checkpoint proof, current recovery
resources and every consumed attempt's applicable data. No production operation
is authorized by this diagnosis. No migration, new checkpoint, stale restore,
production worker startup or production Docker cleanup is part of testing.
