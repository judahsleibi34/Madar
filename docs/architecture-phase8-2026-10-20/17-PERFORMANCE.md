# Bounded preparation measurements

Five local independent runs on sourceff947109 captured150 migrations from both
Git trees and generated an application-only150 plan. Median discovery2.821s;
median plan generation0.0122s. Small sample: no p95/p99 or production capacity
claim. No before/after application optimization is claimed. Raw timings remain
private; source capture has file/total/node/time limits and the parser's additive
path remains deliberately small.

Staging native runs:39 tests25.131s; the44-case kill/lock expansion68.207s;
actual discovered synthetic151/152 candidate plus44 cases74.363s;47 cases with
drift73.630s. These are different suites/repetitions, not performance comparisons.
The HDD-backed shared VM had4vCPU/5.4GiB RAM and roughly12GiBfree at baseline.
Rehearsals are CPU/memory/PID/time bounded and use no public ports. No production
load generator, general speedup, zero-downtime or SLO claim is supported.
