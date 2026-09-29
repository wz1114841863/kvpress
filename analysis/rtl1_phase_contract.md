# RTL1 — Interface / Control Skeleton Bring-up

**Status:** `authorized_by_gate_rtl0_pass; not_functional_rtl_pass`.

RTL1 may not change frozen owners, ports, assertions, oracles, pruning,
admission, scheduler semantics, page size, S2 count, outstanding bounds, merge
format, or physical realization parameters.

| Phase | Scope | Evidence before advance |
|---|---|---|
| RTL1.0 | Top/all skeletons, ports, reset, ready/valid, SVA/TB/scoreboard attachment | compile/elaboration clean; no behavior claim |
| RTL1.1 | R1 identity/fragment/terminal/reset-init/stale suppression | R1 assertions/oracle tests |
| RTL1.2 | R2 eligibility/FIFO/credit/grant-on-accept | R2 assertions/interleavings |
| RTL1.3 | coupled R3/R5 P3/descriptor/atomic publication | durable-only/one-commit assertions |
| RTL1.4 | S2/direct-pending/four-consumer release | generation/stale/GQA assertions |
| RTL1.5 | R6 lifecycle/terminal/retirement/global drain | authority/terminal/retire assertions |
| RTL1.6 | R4 boundary only | packet/fault binding; no exp/FP RTL claim |

CDC/HBM adapter, macro/port count, physical queues, frequency, timing, PPA,
and speedup remain outside RTL1 and require later implementation/Gate-B evidence.

## RTL1.0 progress

**RTL1.0.a structural skeleton: complete.** The Chisel implementation at
`hardware/route_a/chisel/` elaborates the frozen top and nine direct children,
the RTL0.2 logical ready/valid carrier bundles, `core_clk`,
`destructive_reset`, and the sole R1 external-memory carrier. It contains no
registers or mutable architectural state. The required opaque logical fields
have no deployment defaults: only the structural test supplies local values
needed to elaborate a finite carrier shape.

The no-model evidence is the Chisel structural test
`RouteAKVSubsystemTopSpec`; it checks the ten-module hierarchy in CHIRRTL, the
external top port names in in-memory SystemVerilog, the selected anchor widths,
and absence of sequential RTL. CIRCT may optimize inert child shells out of its
final SystemVerilog; that is why hierarchy is checked at the elaborated CHIRRTL
stage rather than by adding non-architectural logic to defeat optimization.

**RTL1.0.b verification binding infrastructure: complete.**
`hardware/route_a/chisel/src/test/resources/rtl1_0_verification_binding.json`
binds every one of the 15 frozen matrix records to its frozen skeleton owner,
one SVA-registry marker, its safety-guarantee or progress-fairness role, and
the one existing Python oracle association. The accompanying zero-port
SystemVerilog registry binds to `route_a_kv_subsystem_top`; it adds no design
behavior or assertion body. The Python
`RouteAScoreboardOracleBindingRegistry` exposes the exact frozen oracle path,
entry-point labels, observation description, and forbidden adapter rule without
dispatching an event or running a model.

Every safety body is explicitly `owner_state_pending`; every progress body is
`owner_event_pending`. This is required because RTL1.0.a has no owner state or
event transitions to observe. The registry proves binding inventory/ownership
consistency only; it is not an SVA/formal proof, Python-scoreboard execution,
directed protocol test, randomized scenario, or RTL functional pass.
Consequently RTL1.0.b does not authorize R1--R6 behavior by itself.
