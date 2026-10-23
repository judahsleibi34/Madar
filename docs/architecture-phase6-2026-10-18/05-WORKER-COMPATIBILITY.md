# Worker consumption and readiness

The deletion worker requires exact protocol2 at NORMAL startup and before every
consuming poll. Schema149 returns no supported deletion protocol; it remains a
negative compatibility boundary. Schema150 publishes2 only at exact schema150.
There is no legacy RPC fallback or direct lifecycle table mutation fallback.

A valid READ_ONLY standby can expose a healthy non-consuming endpoint without
making a prohibited POST protocol RPC. Backend deletion readiness requires a
well-formed positive health response with `consuming: true`; HTTP200 alone does
not prove functional processing. Invalid authority or protocol makes consumption
unhealthy. This correction is covered by worker and readiness regression tests.

The exact a8fac208 native acceptance processed both real synthetic user and tenant
requests through PostgREST and the live deletion container,completed all ten steps,
confirmed actual GoTrue/Storage absence,preserved a foreign tenant/object,and
verified consumption after restarting only that owned staging worker. Delivery,
outbox and deletion markers were150/2/2/2. New source changes require fresh exact
images and acceptance; older receipts are not transferred to a newer commit.

Legacy/manual workers using broad service credentials still require complete
cutover exclusion. Current production supervisor inventory and a real privileged
boot/restart lifecycle are not established by these unit/native checks.
