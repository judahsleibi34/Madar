# Interruption evidence and unproven operation boundaries

| Boundary | Injected condition | Evidence and limitation |
|---|---|---|
| Root credential entry | Held foreign deploy lock or unowned upgrade lock | Actual flock/proc descriptor checks reject before MODEL issuer |
| Root issuance/effect | Issuer refusal, effect exception, credential collision or unlink failure | New lock window released; borrowed lock retained; attempted authorization cleared; prior credential preserved |
| Provider migration entry | Missing actual advisory lock, foreign client or protocol1 | Native SQL rejects; real journal receives no new quiescence record; host/authority are MODEL |
| Backup credential publication | Incomplete restore/replica/inner digest or changed/pending journal | No migration-input record published; actual archive/files/flock, MODEL restore/authority reports |
| Migration147/148/149/150 | Lost reply after actual COMMIT | Authoritative schema observed; same attempt denied; distinct MODEL-authorized forward attempt skips prior SQL |
| Migration147/150 | Actual owned executor-process exit after COMMIT | Running/applying journal cannot imply rollback; session lock released by process death; observed schema retained |
| Full private provider recovery/handoff/worker/proxy/boot | Not executed | No current-head privileged full-operation or guest-reboot PASS |

The existing disposable guest was inspected without booting it or replaying any
historical authority: KVM/dependencies present,1CPU/1024MiB/8GiB,existing attempt
preserved. A prior PhaseVII reboot does not certify this source or operation.
No production authority or full test-domain write handoff was issued.
