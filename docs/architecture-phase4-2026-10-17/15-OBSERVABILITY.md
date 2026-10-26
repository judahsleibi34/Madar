# Signal-to-delivery evidence

The new alert_delivery_rehearsal.py uses actual loopback worker/sink HTTP fixtures
on staging. Existing observer collects ownership-loss, acknowledgement-failure
and backlog-age signals. The receiver first returns503, then accepts the same
stable event ID on retry. Repeated firing is suppressed; clear/recovery delivers
once. Two accepted packets, three POST attempts; all fixture resources close.

This proves collection, evaluation, creation, isolated delivery, retry, suppression
and clear behavior in the drill. It is not an installed production collector or
durable process-restart delivery service. No external destination, credential or
production alert integration is configured. There are no tenant/user metric
labels. Worker counter/gauge separation remains preserved.

Production routing, on-call destinations, durable outbox delivery and complete
backup/WAL/disk/Auth alert coverage remain separate authorized work.
