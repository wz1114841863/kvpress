# DC array-interior proxy materialization — 2026-10-29

**Status:** `PASS_for_pre_DC_input_materialization_only`.

This bounded successor transforms the already frozen paired control-projection
HDL into a **separate remote DC input tree**.  It does not modify Chisel,
re-elaborate either projection, choose a memory macro, run DC, or establish an
area, timing, power, PPA, or common-cost result.

## Exact scope

The deterministic materializer consumes the frozen HDL archive whose SHA-256 is
`335942f0f01c24124b1fda56c6ebbd8b3425afdb2c31220cac04ff871aa94310` and,
using [`../hardware/route_a/dc/dc_array_proxy_v1.json`](../hardware/route_a/dc/dc_array_proxy_v1.json),
replaces only the implementation body of these same-header modules with a
`syn_black_box` proxy:

| Top | Array interior proxy | Retained parent control |
| --- | --- | --- |
| Full-KV | `full_kv_s2_payload_array_boundary` | `FullKVS2GqaSourceWrapper` |
| Route-A | `route_a_m2_entry_array_boundary` | `route_a_m2_production_control_owner` |
| Route-A | `route_a_p3_stage_array_boundary` | `route_a_m2_p3_wrapper` |
| Route-A | `route_a_r5_availability_array_boundary` | `route_a_page_manager` |
| Route-A | `route_a_s2_payload_sidecar_array_boundary` | `route_a_s2_gqa_source_wrapper` |

Thus RMW, prepare/commit/abort, credit, publication, READY, generation/stale,
reclaim, reset, fault, adapters, muxes and fanout remain in the HDL.  The
proxies are not zero-cost: each array interior and all retained peripheral
logic remain `nonzero_unestimated` until a separately authorized physical
realization provides evidence.  Typed top-level external services remain
outside the projection and likewise nonzero/unestimated.

## Remote evidence

The corrected `r1` materialization ran on the EDA server with exit marker
`KVZAP_DC_ARRAY_PROXY_MATERIALIZE_R1_EXIT=0`.  Its generated package remains
at:

```text
/home/yaz80/wz_project/chisel_projects/kvpress/artifacts/
  qwen3_8b_32k_s1_control_projection_v1_dc_array_proxy_v1_r1/
```

[`dc_array_proxy_materialization_20261029.json`](dc_array_proxy_materialization_20261029.json)
records `pass: true`, all five boundaries, unchanged Full-KV `1` and Route-A
`182` filelist entries, and the proxy/header hashes.  A second independent
checker records the same five proxy bodies and retained parents in
[`dc_array_proxy_check_20261029.json`](dc_array_proxy_check_20261029.json).

The earlier failed `..._dc_array_proxy_v1` output was removed after the `r1`
check passed; no frozen HDL archive or successful `r1` output was removed.

## Parent-control semantic non-regression

The proxy generator does not alter Chisel sources.  Nevertheless, the EDA
server ran the selected parent-control regression on the same workspace after
materialization:

| Evidence | Actual tests | Result |
| --- | ---: | --- |
| `FullKVMeasurementDutSpec` | 5 | PASS |
| `DualMeasurementDutStructuralSpec` | 3 | PASS |
| `RouteAM2ProductionControlOwnerSpec` | 5 | PASS |
| `RouteAP3StageArrayBoundarySpec` | 1 | PASS |
| `RouteAR5AvailabilityArrayBoundarySpec` | 1 | PASS |
| `RouteAPackedS2ReadPathSpec` | 6 | PASS |
| `RouteAReclaimSpec` | 5 | PASS |
| `RouteAPackedActivationCompositionSpec` | 3 | PASS |
| `RouteAResetEpochIntegrationSpec` | 4 | PASS |
| **Total** | **33** | **PASS** |

The initial reset selector had an incorrect package name and reported `0/0`;
it is excluded and was replaced by the 4-test integration selector above.
`RouteAMeasurementDutR3Spec` remains **not executed** in this batch: its
full-root ChiselSim testbench fails while compiling the generated C-DPI bridge
for the deep B2c nested association port (`*Impl_*` symbols are absent from
the Verilator declarations).  This occurs before its four assertions run and
is neither a proxy-body check nor evidence of a production RTL failure.  It
remains a separately bounded full-root test-observation/harness repair; the
33 passing tests must not be represented as a substitute for it.

## Consequence and remaining gate

This removes the sole *structural* array-interior materialization blocker in
the prior input-readiness review.  The paired package is ready to enter a
**separately authorized** first DC-feasibility run under
`dc_feasibility_fair_v1`; the run must still prove DC parser/elaboration/link
success, apply the frozen SDC, and emit native `check_timing`, constraint and
unconstrained-path reports.  It may not be presented as a macro choice or a
PPA/net-benefit result.
