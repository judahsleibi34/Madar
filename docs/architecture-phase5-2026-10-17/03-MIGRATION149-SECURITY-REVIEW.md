# Independent149 SQL review

Published149 remains8ed767df57f5c02be50d83621fe45d314b3d1fdb42d2b7a470170519bdf1f869
in both trees. No confirmed new defect in its delivery/outbox generation or scoped
cancellation SQL. Locked finish samples database clock after waits; resolution
rechecks after materialization and rolls back inserted deliveries and status on
expiry; legacy/public helper paths and direct mutation grants remain denied.
Two new native resolver-first/cancellation-first lock-order cases PASS.

Three other native deletion-state invariants FAIL in retained083 application
helpers. Those failures are not falsely attributed to149 or fixed by its narrower
cancellation function. See07. Runtime service-role bypass remains privileged and
requires application/DB operation boundaries; no anonymous bypass was demonstrated.
