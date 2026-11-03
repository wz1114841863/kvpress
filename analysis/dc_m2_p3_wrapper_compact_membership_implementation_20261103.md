# M2/P3 wrapper compact-membership implementation — 2026-11-03

## Scope

This record closes the functional RTL batch for the first bounded candidate
from `dc_m2_p3_wrapper_p0_diagnosis_20261103.md`.  It changes only the
`route_a_m2_p3_wrapper` internal membership representation and directed test
witnesses.  It does not change pruning, admission, R3 publication, R6
authority, R2 arbitration, the Route-A clock, Full-KV scope, or any external
service boundary.

This is functional and source-representation evidence.  It is not generated
HDL closure, mapped area, timing, lint, power, PPA, speedup, or hardware net
benefit.

## Implemented representation

The former per-member copies of `AdmissionContext` and
`PendingPayloadReadBinding` are replaced by:

- a 79-bit member record containing `logical_position` and `payload_ref`;
- an 80-bit pending-read suffix containing transaction identity, payload
  handle, source generation, and destination endpoint.

Layer and ordinal remain the existing table indices.  Head, valid count and
group tag remain the already validated stage header.  Publication reconstructs
`entry_id` from the frozen coordinate equation
`logical_position * 288 + layer * 8 + kv_head`.  The full reconciliation
journal is unchanged.

The P0 source-accounting expectation is therefore unchanged: wrapper raw state
should fall from 990,322 to approximately 400,498 bits, a 589,824-bit source
reduction.  The pre-DC mapped-sequential ceiling remains 76,032 cells because
the accepted DDC had already optimized most duplicated fields.  Neither figure
is a mapped result for this implementation.

## Functional validation

The final remote clean regression ran in
`kvzap-control-refine:p8-compact-full` with retained log:

```text
/home/yaz80/wz_project/chisel_projects/kvpress/logs/
  compact_membership_p1_full_regression_20261103.log
```

Its enclosing marker is
`KVZAP_COMPACT_MEMBERSHIP_P1_FULL_REGRESSION_EXIT=0`.  All 14 suites completed:
57 tests succeeded, with zero failures, aborts, cancellations, ignored tests,
or pending tests.  This combines the 16 focused wrapper checks with the 41
selected cross-stage non-regression checks.

The first aggregate run exposed a stale integration witness and ended 56/57.
The production wrapper was not weakened.  The test-only harness was repaired
to initialize later-added inputs, wait for actual admission and P3 storage
handshakes, expose the real R3-owned M2 request/publication-candidate outputs,
and return fully matched M2 provenance.  The repaired single test passed 1/1
locally and remotely before the clean aggregate rerun.

The directed nonzero-layer/head publication case checks that the compact
record reconstructs `entry_id`, layer and head correctly and remains stable
under output backpressure.  Existing materialization, pack-read,
reconciliation, publication, authority, direct-pending, four-consumer,
Full-KV and Route-A measurement contours remain green in the named suite set.

## Disposition and next gate

The compact-membership **functional batch passes**.  The next bounded batch is
to generate a new immutable 48-file successor and independently recheck:

1. all 16 typed top-port families;
2. all 12 non-black-box production owners;
3. the four raw Route-A array interiors and five paired typed proxies;
4. actual generated wrapper state and the expected compact member fields;
5. absence of the former full-record backing fields.

No same-fair-v1 DC run is authorized by this functional pass alone.
