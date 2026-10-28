# Paired S2 payload access-map and common-equivalence disposition

**Status:** `payload_access_role_mapped_not_cancellable` (2026-10-28).

This bounded successor records actual Chisel parent/child paths. It is neither
a selected SRAM interface nor an inference from both contours having four
consumers. It does not change the frozen measurement cut, select a macro,
clock or latency, run DC/CACTI, or establish an area/energy/PPA result.

## Scope

- Route-A parent/child: `RouteAS2GqaSourceWrapper` /
  `RouteAS2PayloadSidecarArrayBoundary`.
- Full-KV parent/child: `FullKVS2GqaSourceWrapper` /
  `FullKVS2PayloadArrayBoundary`.
- The actual control-top projections remain `RouteAMeasurementDut` and
  `FullKVMeasurementDut`.
- Route-A sidecar, packed lease/page association, R3/R5/R6 authority, R2
  arbitration, and baseline lifecycle are not merged by this payload map.

## Actual payload access map

| Access role | Route-A parent-to-child path | Full-KV parent-to-child path | Disposition |
| --- | --- | --- | --- |
| write | Checked `s2_payload_fragment_in.fire` is captured as `{slot, fragment, data}`; `payload_write_ack.fire` advances parent `payloadNext`. | Checked `payload_in.fire` is captured as `{slot, fragment, data}`; `write_ack.fire` advances parent `next`. | Same parent-authorized write/ack role. |
| read | READY/identity/generation/range check, one child read, exact `{slot, fragment}` match, parent-held response. | READY/identity/generation/range check, one child read, exact `{slot, fragment}` match, parent-held response. | Same one-outstanding read/held-response role. |
| array-child ownership | Child stores only payload coordinates/data. | Child stores only payload coordinates/data. | Neither child owns identity, generation, READY, terminal/fault, consumers, release, selection, or authority. |
| READY/release | Packed lease/fill-open plus terminal and optional sidecar completion, then four packed commits. | Baseline fill-open plus write-ack-complete terminal, then four baseline commits. | Observable release discipline is comparable; prerequisite owners and carriers are not identical. |
| reset/stale/fault | Route-A slot/packed source state and Route-A lifecycle. | Baseline-local state and `FullKVTerminalRetireAdapter`. | Fail-closed intent is comparable; shell logic is not identical. |

## Non-equivalences retained as nonzero cost

1. Route-A has a `s2_sidecar_access_v1` child/protocol. Full-KV does not gain
   sidecar or packed-page logic merely to improve an accounting comparison.
2. Route-A payload coordinates are the fixed 9-bit/512-fragment S2 anchor.
   Full-KV coordinates use `p.coreMemoryFragmentIndexWidth`; its focused
   wrapper test elaborates 3 bits, while dual structural elaboration uses 9.
   Matching future geometry is a condition, not current evidence.
3. Route-A fill provenance is a packed lease/page association with optional
   sidecar completion. Full-KV fill comes from the baseline read producer.
4. Route-A uses packed `SourceInstance` and R6 lifecycle; Full-KV uses a
   baseline `{s2_slot, source_generation}` and baseline terminal/retire path.

## Common-equivalence disposition

`s2_payload_access_v1` is **logical-access-role mapped**, but remains
`not_cancellable_pending_same_parameter_shell_and_paired_conformance`.
Both payload interiors and parent adapters stay named, nonzero candidate-top
costs. Route-A sidecar and packed controls remain Route-A incremental
`unestimated_not_zero`.

Any payload cancellation requires all of the following before a new decision:

1. matching 9-bit payload geometry in both future synthesis shells;
2. an explicit equal payload-wrapper mapping, not a whole-array port;
3. paired reset/init, stale, fault, release and response-hold conformance;
4. a successor source/port/filelist freeze and regression on those exact
   shells.

Only R2/R1/registry/router retain their separate
`eligible_common_after_identical_shell` disposition. This record changes no
current cancellation or A4 accounting.

## Verification record

`tests/test_s2_paired_access_map_common_equivalence.py` guards the source map.
Functional prerequisites are Route-A S2 directed `9/9`, Route-A four-consumer
`3/3`, and Full-KV wrapper plus dual structural `8/8` in
`fullkv_s2_directed_rerun.log`, `FULLKV_S2_RERUN_EXIT=0`. The Full-KV evidence
uses the actual parent-to-child access path, not a fixture, tie-off, or
zero-test selector.

The successor paired 9-bit regression then ran `FullKVMeasurementDutSpec` 5/5
and `RouteAPackedS2ReadPathSpec` 6/6 together (`s2_paired_9bit_conformance_20261028.log`,
`S2_PAIRED_9BIT_CONFORMANCE_EXIT=0`). It removes the focused 3-bit geometry as
a conformance gap, while preserving this record's non-cancellation: the two
parents/wrappers remain distinct and Route-A sidecar, packed lease/page and R6
controls stay Route-A incremental.
