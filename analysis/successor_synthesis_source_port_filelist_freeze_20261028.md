# Successor synthesis source/port/filelist freeze — 2026-10-28

**Status:** `source_port_filelist_frozen_paired_shell_conformance_pending`.

This is the successor to the immutable functional cut at `fc06fdbc`. It fixes
the exact current control-top Scala dependency closure, outer interfaces, build
inputs, and intentional exclusions after the M2/R5/P3/S2 wrapper successors.
The machine-readable hashes and full lists are in
[`successor_synthesis_source_port_filelist_freeze_20261028.json`](successor_synthesis_source_port_filelist_freeze_20261028.json).

It is not a selected physical implementation, generated-Verilog filelist,
macro mapping, clock/reset choice, DC run, or PPA conclusion.

## Selected control tops and source closure

The two conditional candidates remain `FullKVMeasurementDut` and
`RouteAMeasurementDut`. The frozen Scala source closure contains twelve main
sources plus `build.sbt` and `project/build.properties`; every file is
SHA-256 pinned in the JSON. `RouteAKVSubsystemTop` is excluded because it is
the rejected composition-only skeleton. `RouteAM2EntryStorage` is excluded
because it is an uninstantiated Package-A unit candidate, not a dependency of
the current production M2 control owner. All test sources, including the
flat full-root P3 observation harness, are verification-only.

The Full-KV successor explicitly adds the live payload access ports
`full_kv_payload_read_req_in` and `full_kv_payload_read_rsp_out` to the
previous cut's outer list. Route-A retains its owner-to-owner internal
publication/activation/lease paths; those are not reintroduced as top ports.
The direct-pending scope remains `valid_count=1`.

## Paired S2 geometry disposition

The current source can elaborate either selected top with a 9-bit fragment
index. That fact is only an interface capability. The focused Full-KV
functional wrapper regression used a 3-bit geometry, while the Route-A packed
anchor is 9-bit/512-addressable fragments. The two cannot support payload or
adapter cost cancellation.

The next bounded conformance batch must use one explicit 9-bit parameter vector
on both shells and cover reset/init, stale, fault, release, and held payload
response behavior. It must also demonstrate an equal wrapper mapping. Until
then, both payload interiors/adapters remain nonzero and the Route-A sidecar,
packed lease/page and R6 controls remain Route-A incremental.

## Evidence and next gate

The immediately preceding P3 full-root test repair passed 3/3, and its P3/R3-R5
adjacent non-regression passed 7/7, both with remote exit marker zero. This
freeze merely records the source boundary those results exercised; it does not
convert them into physical or common-cost evidence.

The next gate is the bounded same-parameter S2 shell-conformance regression,
followed by a disposition that either proves the allowed common subset or keeps
the actual shells separately costed. No DC/CACTI/PPA work is authorized.
