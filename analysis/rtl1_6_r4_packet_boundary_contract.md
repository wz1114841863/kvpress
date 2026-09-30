# RTL1.6 — R4 packet/fault boundary closure

## Status and boundary

**Status:** `complete_r4_packet_boundary_control_at_module_scope; top_integration_and_numeric_core_pending`.

RTL1.6 closes only the replaceable R4 packet/result/fault boundary selected by
Gate-A R4. It does not implement online-softmax arithmetic, `exp`, binary32
arithmetic, accumulator precision, lane storage, RF/SRAM/spill, source mux,
controller, timing, throughput, PPA, model/GPU execution, accuracy, or a new
A4 DSE. The top keeps all new carriers inactive until a later integration
phase.

## Why the legacy carrier is not reused

The existing `SourcePartial` is a pre-RTL opaque boundary containing only a
source kind, one 128-bit word, and one 512-bit word. It has no transaction
identity, consumer identity, fragment ordinal, `last`, or packet association.
RTL1.6 must therefore not reinterpret it as the R4 packet protocol. It remains
present and inert for compatibility; the following local carriers hold the
frozen packet meaning.

## New local carriers

| Carrier | Fields | Meaning |
|---|---|---|
| `r4_partial_header` | `(request_id, incarnation)`, 128-bit header | One frozen R4 header with identity. |
| `r4_value_fragment` | identity, `fragment_index[2:0]`, `last`, 512-bit data | One of the ordered eight logical 64-B present-partial fragments. |
| `r4_result_stub` | identity, 4,096-bit normalized value | Success input from a future replaceable numeric implementation. |
| `r4_numeric_fault` | identity | Explicit fail-closed numeric-fault input from that implementation. |

All are core-local logical ready/valid channels. They are not HBM commands,
physical ports, selected arithmetic storage, or a new top-level interface.

`r4_result_stub` and `r4_numeric_fault` are mutually exclusive terminal facts
for one active merge identity. The R4 boundary maps either one to the existing
`merge_rsp_or_numeric_fault` status channel consumed by R6; it does not create
another outward terminal path.

## Frozen packet checks for RTL1.6 behavior

The later control-only parser must check only frozen structural facts:

- source ordinal is `hot=0`, `pending=1`, or `packed=2`;
- consumer ID is in `0..3`, merge instance is zero, and reserved bits are zero;
- a present header declares eight fragments; an absent header declares zero;
- an absent header exactly encodes binary32 `m=-infinity` and `l=+0`;
- present fragments are ordered `0..7` and only fragment 7 has `last`.

The parser does not decide whether present binary32 `m/l/o` values are finite,
whether `l > 0`, whether `exp` overflows, or whether a normalized value is
correct. Those are explicitly deferred numeric-core responsibilities. It also
does not impose a source-order schedule, prove complete merge membership, or
reorder sources: canonical ordering remains a frozen semantic property of the
future numeric implementation and Python oracle.

## Evidence and next step

RTL1.6.0 is synthesizable-interface and elaboration evidence only. RTL1.6
adds a control-only parser, one active merge association, stable
commit/terminal outputs, and directed no-model ChiselSim. It binds no numeric
quality, binary32 arithmetic, cycle, latency, controller, PPA, or end-to-end
top-level claim.

## RTL1.6 module-control binding

`RouteAMergeBoundary` accepts an absent header only when it encodes the frozen
absent identity exactly. It accepts a present header only when it declares
eight fragments, then accepts exactly fragment ordinals `0..7` with `last` on
fragment seven alone. A structurally malformed header or fragment remains
unaccepted; it does not create a commit or a terminal outcome. The module
retains packet control only: it neither stores nor interprets the binary32
`m/l` fields or the 128-bit value lanes.

For a nonempty `merge_req`, a matching `r4_result_stub` or
`r4_numeric_fault` may create exactly one existing R6-facing terminal response.
The former forwards the frozen success status and the latter forwards the
frozen numeric-fault status with a zero result payload. Empty, stale,
duplicate, or simultaneous terminal facts are unaccepted. R6 remains the
unique outward terminal consumer.

`RouteAMergeBoundarySpec` is the no-model directed ChiselSim evidence for
positive absent/present packets, malformed headers/fragments, stable
backpressure, and result/fault association across all nonempty source-presence
masks. The Python numeric reference remains the golden source for binary32
merge semantics; this module is not numeric RTL.
