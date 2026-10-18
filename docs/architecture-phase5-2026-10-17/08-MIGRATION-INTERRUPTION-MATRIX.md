# Native committed-state interruption evidence

| Failure | Actual preserved state | Required future action |
| --- | --- | --- |
|Before147/provider resurrection/idle foreign session|146|Reject beforeSQL;fresh verified operation|
|SQL error during147|146|Transaction rollback;do not reuse consumed journal|
|Lost commit147 orSQL error148|147,delivery2|READ_ONLY;fresh authorized forward repair|
|Lost commit148 orSQL error149|148,delivery2|READ_ONLY;old resolver/deletion activation forbidden|
|Lost commit149|149,delivery2/outbox2|No fabricated completion;new protected reconciliation|
|Separate authorized forward after147|149|Sealed completion stillnot NORMAL authority|
|SQLfile replaced after verification|149,approved bytes only|Replacement never executes|

All11 new native executor cases PASS within122 retained/new executions. Transport
authority and consumer/provider checks are fixtures; transactions/commits/ACLs/
journals are real. Six native provider fence-effect children were also interrupted
and reconciled without replay; DB restart retained NOLOGIN. Full privileged
installer/systemd/proxy/authority/replica interruption execution is NOT TESTED.
