# R5 descriptor-externalized Route-A successor input freeze

**Status:** `pre_proxy_source_input_verified` (2026-10-29).

This record freezes the successor Route-A source input produced after R5
descriptor externalization.  It supersedes neither the paired v1 HDL freeze
nor its Full-KV source: Full-KV is copied unchanged from that freeze.  This is
not a DC feasibility result, macro choice, PPA result, or external-service
cost measurement.

## Immutable source package

| Item | Value |
| --- | --- |
| profile | `qwen3_8b_32k_s1_control_projection_v1` |
| Route-A source commits | `ae24e2c` externalization, `f99ca9a` liveness-replica removal |
| archive | `hardware/route_a/chisel/generated/qwen3_8b_32k_s1_control_projection_r5_descriptor_externalized_v1/paired_control_projection_r5_descriptor_externalized_v1.tar.gz` |
| archive SHA-256 | `9d58f0df438555dba433390b9db2c4f5a1e85fee67e431d142b60d026b810093` |
| Route-A SV closure | 48 files, 473,720,822 B |
| Route-A closure SHA-256 | `bd51c1aac832af2819189b7359a7adc7c12da767df2d36e2546f3fdc9487543b` |
| Route-A filelist | `route_a_control_projection_successor.f` |

The package contains the unchanged `full_kv_control_projection.sv` and its
independent filelist, plus the new split Route-A directory and successor
relative filelist.  Its machine-readable check and manifest are retained in
the same generated directory.

## Structural result

`check_r5_descriptor_externalization_successor.py` passed on the remote
generated source tree.  It proves the 48-entry Route-A filelist is closed,
contains exactly one `route_a_control_projection` top, exports both typed
`functional_r5_descriptor_service` request/response valid ports, excludes
`descriptorEntryImage`, `descriptorReadable`, and `descriptorValidRecords`,
and retains nonempty `route_a_page_manager`, `route_a_m2_p3_wrapper`, and
`route_a_s2_gqa_source_wrapper` parents.

The split flow is necessary because monolithic firtool lowering of the full
Route-A root exits 139; the source remains the complete root CHIRRTL and the
recovery only changes output partitioning.  The `route_a_page_manager.sv`
remains large because parent control, R5 availability/generation, reclaim
state and assertion shadow are deliberately retained.  This is not evidence
that the removed functional descriptor backing remains present.

## Next input transformation

The next bounded step is to apply the already-approved typed array-interior
proxy materialization to this successor package, using a new manifest and
without modifying the frozen v1 package.  The resulting paired proxy source
root—not this unproxied split source—will become the Route-A input to the next
DC feasibility successor.  R5 descriptor service remains a typed top-level
external boundary with nonzero, unestimated capacity, latency, bandwidth,
controller/PHY and energy cost.
