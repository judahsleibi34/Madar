#!/usr/bin/env python3
"""Exercise real notification leases/retry/dead-letter SQL, rolling fixtures back."""

import json
import secrets

import manage


def main():
    manage.require_database_marker()
    fixture = json.loads((manage.RUNTIME / "smoke-fixture.json").read_text())
    tenant, user = int(fixture["tenant_id"]), int(fixture["worker_user_id"])
    key = secrets.token_hex(16)
    manage.compose("stop", "--timeout", "15", "notification-worker")
    try:
        manage.sql(f"""
begin;
do $$
declare identifier uuid; first_claim public.notification_deliveries;
 second_claim public.notification_deliveries; final_claim public.notification_deliveries;
 finished public.notification_deliveries; available timestamptz; amount integer;
begin
 insert into public.notification_deliveries(tenant_id,user_id,channel,template,deduplication_key,max_attempts)
 values({tenant},{user},'internal','synthetic-recovery','{key}',3) returning id into identifier;
 select * into first_claim from public.claim_notification_deliveries(1,clock_timestamp(),30);
 if first_claim.id is distinct from identifier or first_claim.attempts<>1 then
   raise exception 'synthetic first lease assertion failed'; end if;
 -- A worker disappears after claiming and before acknowledgement.
 select * into second_claim from public.claim_notification_deliveries(1,first_claim.processing_lease_until+interval '1 second',30);
 if second_claim.id is distinct from identifier or second_claim.attempts<>2 then
   raise exception 'synthetic expired lease recovery assertion failed'; end if;
 available:=second_claim.processing_started_at+interval '60 seconds';
 finished:=public.finish_notification_delivery(identifier,'retry','synthetic_transient',null,available,null,second_claim.processing_started_at);
 if finished.status<>'pending' then raise exception 'synthetic retry assertion failed'; end if;
 select count(*) into amount from public.claim_notification_deliveries(1,available-interval '1 second',30);
 if amount<>0 then raise exception 'synthetic backoff assertion failed'; end if;
 select * into final_claim from public.claim_notification_deliveries(1,available,30);
 if final_claim.id is distinct from identifier or final_claim.attempts<>3 then
   raise exception 'synthetic retry claim assertion failed'; end if;
 finished:=public.finish_notification_delivery(identifier,'retry','synthetic_exhausted',null,available+interval '60 seconds',null,available);
 if finished.status<>'dead' or finished.dead_at is null then
   raise exception 'synthetic dead letter assertion failed'; end if;
 select count(*) into amount from public.claim_notification_deliveries(1,available+interval '1 day',30);
 if amount<>0 then raise exception 'synthetic terminal delivery reclaimed'; end if;
end $$;
rollback;
""")
        print("PASS actual SQL claim, worker-loss lease expiry, reclaim, bounded retry availability, exhausted-attempt dead letter and terminal exclusion; fixture rolled back")
    finally:
        manage.compose("start", "--wait", "--wait-timeout", "60", "notification-worker")


if __name__ == "__main__":
    main()
