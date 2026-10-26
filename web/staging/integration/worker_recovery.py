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
 finished public.notification_deliveries; amount integer; outcome text;
begin
 insert into public.notification_deliveries(tenant_id,user_id,channel,template,deduplication_key,max_attempts)
 values({tenant},{user},'internal','synthetic-recovery','{key}',3) returning id into identifier;
 select * into first_claim from public.claim_notification_deliveries_v2(1,30);
 if first_claim.id is distinct from identifier or first_claim.claim_generation<>1 then
   raise exception 'synthetic first lease assertion failed'; end if;
 update public.notification_deliveries set processing_lease_until=clock_timestamp()-interval '1 second' where id=identifier;
 select * into second_claim from public.claim_notification_deliveries_v2(1,30);
 if second_claim.id is distinct from identifier or second_claim.claim_generation<>2 then
   raise exception 'synthetic expired lease recovery assertion failed'; end if;
 foreach outcome in array array['sent','retry','dead','revoked'] loop
   begin
     perform public.finish_notification_delivery_v2(identifier,first_claim.claim_generation,outcome);
     raise exception 'synthetic stale finish was accepted';
   exception when raise_exception then
     if sqlerrm<>'notification_delivery_claim_lost' then raise; end if;
   end;
 end loop;
 finished:=public.finish_notification_delivery_v2(identifier,second_claim.claim_generation,'retry','synthetic_transient',null,60);
 if finished.status<>'pending' or finished.available_at<=clock_timestamp() then raise exception 'synthetic retry assertion failed'; end if;
 select count(*) into amount from public.claim_notification_deliveries_v2(1,30);
 if amount<>0 then raise exception 'synthetic backoff assertion failed'; end if;
 update public.notification_deliveries set available_at=clock_timestamp()-interval '1 second' where id=identifier;
 select * into final_claim from public.claim_notification_deliveries_v2(1,30);
 if final_claim.id is distinct from identifier or final_claim.claim_generation<>3 then
   raise exception 'synthetic retry claim assertion failed'; end if;
 finished:=public.finish_notification_delivery_v2(identifier,final_claim.claim_generation,'retry','synthetic_exhausted');
 if finished.status<>'dead' or finished.dead_at is null then raise exception 'synthetic dead letter assertion failed'; end if;
 select count(*) into amount from public.claim_notification_deliveries_v2(1,30);
 if amount<>0 then raise exception 'synthetic terminal delivery reclaimed'; end if;
end $$;
rollback;
""")
        print("PASS protocol2 SQL generation, lease expiry/reclaim, four stale outcome denials, bounded retry/dead letter; fixture rolled back")
    finally:
        manage.compose("start", "--wait", "--wait-timeout", "60", "notification-worker")


if __name__ == "__main__":
    main()
