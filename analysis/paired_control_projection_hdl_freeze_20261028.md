# Paired control-projection generated HDL freeze — 2026-10-28

**Status:** `generated_hdl_pre_dc_input_frozen`.

This record closes the approved bounded control-projection generation batch.
It freezes actual SystemVerilog compilation units for the two selected control
tops, not a new functional contour or a physical implementation result.  The
machine-readable companion is
[`paired_control_projection_hdl_freeze_20261028.json`](paired_control_projection_hdl_freeze_20261028.json).

## Frozen profile and source scope

Both projections use the explicit
`qwen3_8b_32k_s1_control_projection_v1` parameter object from
`RouteASynthesisControlProjectionProfile`; it is the bounded Qwen3-8B,
32K-context, single-sequence control anchor.  It does not select a memory
macro, physical port/latency, clock/frequency, HBM controller, R4 numeric
implementation, or PPA target.

The source/outer-interface baseline remains the approved
[`successor_synthesis_source_port_filelist_freeze_20261028.md`](successor_synthesis_source_port_filelist_freeze_20261028.md).
This successor adds only the explicit profile, projection HDL emitter and
structural verifier.  `RouteAKVSubsystemTop`, all `src/test` sources, and the
fixture-only `RouteAM2EntryStorage` remain excluded from synthesis input.

| Projection | Generated top | Compilation-unit form | File count |
| --- | --- | --- | ---: |
| Full-KV | `full_kv_control_projection` | one SystemVerilog file | 1 |
| Route-A | `route_a_control_projection` | firtool split-SystemVerilog directory | 182 |

Each top has an independent `.f` file.  They must not be passed to one tool
invocation together, because the independent compilation units define common
module names.

## Artifact and integrity

The committed artifact is
[`paired_control_projection_hdl_qwen3_8b_32k_s1_control_projection_v1.tar.gz`](../hardware/route_a/chisel/generated/qwen3_8b_32k_s1_control_projection_v1/paired_control_projection_hdl_qwen3_8b_32k_s1_control_projection_v1.tar.gz).

| Item | Value |
| --- | --- |
| Archive entries | 192 |
| Archive SHA-256 | `335942f0f01c24124b1fda56c6ebbd8b3425afdb2c31220cac04ff871aa94310` |
| Full-KV top SV SHA-256 / size | `5e4d9918030e3d517d9913ff7c56e2325bd3c1f640e1a844d88a8a4473792256` / 822,385 B |
| Route-A top SV SHA-256 / size | `af8d7d2c5d2cb30f9adbc0f6d3f8bc06425b7020652d91cee0bae400c3b88de7` / 1,338,526 B |
| Both compilation units, including split support SV | 183 SV files / 738,300,596 B |

`paired_control_projection_hdl_check.json`, contained in the archive, stores
SHA-256 values for every file in both compilation units.  It passed the exact
recursive Route-A filelist comparison (all 182 SV files, including nested
verification support) and the Full-KV one-file filelist comparison.

## External boundary and structural evidence

The check requires actual generated top-level valid signals, not test driver
names.  Full-KV retains read work, `external_core_mem_if_v1`, payload
read/request-response, four-consumer commit, terminal and retire boundaries.
Route-A retains the frontend/lifecycle, R3/R6 source-plan and pending-descriptor
inputs, hot/pending bindings, `external_core_mem_if_v1`, typed functional
sidecar work/release/allocation/issue, typed partial offers/fragments, and the
typed R4 packet/merge/result/fault boundary, plus terminal and retire.

The generated Route-A unit contains none of the following retired references:
`route_a_kv_subsystem_top`,
`route_a_functional_sidecar_delivery_adapter`,
`route_a_functional_partial_provider_boundary`, or
`route_a_functional_r4_reference_boundary`.  These checks do **not** claim
that a later synthesis optimizer will retain every control register; that is a
separate DC-feasibility check.

Functional sidecar delivery, partial provision, R4 numeric work, external
memory service, P3 backing, and R5 descriptor service remain typed external
boundaries with nonzero, unestimated cost responsibility.  The Route-A
direct-pending result remains the approved `valid_count=1` contour only.

## Generation and regression evidence

Generation used Chisel 7.15.0, sbt 1.11.5, Java 11.0.19, and CIRCT firtool
1.158.0 on the remote EDA Chisel platform.  Full-KV generated directly through
`ChiselStage.emitSystemVerilog`.  The Route-A top first generated its unchanged
full-root CHIRRTL (684,686,696 B), then firtool emitted the same CHIRRTL with
`--format=fir -O=debug --mlir-disable-threading --strip-debug-info
--lowering-options=locationInfoStyle=none,emittedLineLength=160 --split-verilog`.
This diagnostic recovery avoids the tool's monolithic firtool exit-139 path;
it neither changes a production owner nor substitutes a narrower probe.

The structural verifier passed for both units.  Nine post-emission semantic
suites passed 34/34 actual tests: profile (1), projection elaboration (1),
Full-KV (5), R3/R5 publication (6), packed-S2 (6), four-consumer (3), reclaim
(5), reset integration (4), and packed activation (3).  The final full-root
dual-DUT structural guard passed 3/3 using CHIRRTL elaboration.  It replaces
only ChiselSim's failing generated Verilator DPI wrapper for a deep B2c
carrier; both original complete roots remain unchanged and are elaborated.

## Cost and next gate

Emission adds no hardware-function cancellation or zero-cost classification.
The companion BOM delta explicitly preserves all parent adapters, mux/fanout,
control state, logical array wrappers and external services as nonzero or
unestimated.

This is a valid pre-DC HDL input freeze, **not** a DC-feasibility PASS.  A
separately authorized DC-feasibility run still needs a target standard-cell
library/link setup, clock and reset constraints, black-box/memory treatment,
per-top independent filelist invocation, and declared treatment of every
external typed service.  It must also check actual netlist connectivity and
optimization; no area, timing, power, macro, HBM, numeric, common-cost
cancellation, multi-record direct-pending, or KVZap net-benefit conclusion is
made here.
