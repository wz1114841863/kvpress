# Dual synthesis-top input package — 2026-10-28

**Status:** `input_inventory_prepared_projection_generator_and_externalization_pending`.

This package turns the current successor source/port freeze into an exact pre-DC
inventory for the two conditional control-top projections. It does **not**
generate HDL, select an implementation parameter profile, add a top wrapper,
run DC, or make an area/timing/power claim. The machine-readable record is
[`dual_synthesis_top_input_package_20261028.json`](dual_synthesis_top_input_package_20261028.json).

## Fixed input inventory

The only projection sources are `FullKVMeasurementDut` and
`RouteAMeasurementDut`. Their exact Scala dependency closure, SHA-256 values,
build inputs, and outer port inventories are inherited from
[`successor_synthesis_source_port_filelist_freeze_20261028.json`](successor_synthesis_source_port_filelist_freeze_20261028.json).
The JSON repeats both ordered outer-port lists and the twelve admissible
main-source paths so a future generator review can reject an accidental source
or port change.

`RouteAKVSubsystemTop` remains excluded because it is a composition-only
skeleton with inactive ties. `RouteAM2EntryStorage` remains excluded because it
is an uninstantiated fixture-only candidate, not in the production M2 control
closure. All test code and observation harnesses remain excluded.

The paired 9-bit S2 regression provides a common *functional-conformance*
profile only: Full-KV passed 5/5 and Route-A passed 6/6 with the named R2/R1/S2
fields matched. Its `testOnlyAnchor` R6 encoding and remaining test settings
are not a deployment, macro, timing, or area configuration. A future generator
must receive one separately approved complete `RouteASkeletonParameters`
profile; it may not silently use the test profile.

## Retained logic and boundaries

The Full-KV projection retains its actual baseline-local producer,
delivery-context bridge, R2/R1/registry/router, S2 endpoint/wrapper, terminal
adapter and status collector. The Route-A projection retains R3/R6, hot,
direct-pending, M2/R5/P3, packed activation, R2/R1/context/router, S2 and all
parent-owned wrapper peripherals. A projection may not tie off a missing
producer or turn a Route-A-only sideband into fabricated baseline behavior.

M2, P3, R5 and S2 are array-only: only the isolated logical array interiors
are later wrapper/proxy candidates. Lookup/RMW, prepare/commit/abort,
publication, credit, stale, reclaim, READY, four-consumer, reset/fault and
access-adapter peripherals remain control RTL.

`external_core_mem_if_v1` remains a real external typed service on both
projections. Route-A pending backing and R5 descriptor storage retain nonzero
external-service responsibility through it. The functional sidecar-delivery,
partial-provider and R4 reference classes must be externalized in a later
projection module; they must not become synthesized control or tie-offs. Their
named outer contracts and nonzero cost rows are retained here.

## Why this is not a DC filelist

The current parameterized measurement-DUT constructors cannot be sent directly
to DC: no dedicated control-projection generator exists, and the Route-A DUT
still instantiates functional reference classes that the approved candidate
definition excludes. This package is therefore an **input inventory**, not
generated SystemVerilog or a DC `.f` closure.

The next bounded action needs separate approval: create paired
control-projection generator(s), externalize the three functional-reference
boundaries through typed top-level connectivity, choose one complete parameter
profile explicitly, refresh the source/port/filelist freeze, and rerun the
semantic regressions. Only then can a distinct DC-feasibility request be
considered. S2 remains non-cancellable: its same-parameter behavior is
covered, but the Full-KV and Route-A shells, sidecar, packed page/lease and R6
controls are not the same implementation.
