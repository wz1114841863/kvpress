# RTL3.9-B1 — R3 automatic packed-write activation

**Status:** `complete_functional_p3_packed_write_activation`.

RTL3.9-B1 closes the narrow reachability gap identified by B0: once the
RTL3.9-A materialized P3 record is complete, the pre-existing R3-owned
packed-write sequencer, existing delivery-context composition, R2/R1,
registry, and typed router form the only production-shaped write path.
No new top-level carrier is activated.

```text
R3 COMPLETE (exact payload + sidecar)
  -> R3 packed-write candidate (request, then eight write-data fragments)
  -> existing delivery-context allocation / R2 / R1
  -> existing typed R3 packed-write terminal
  -> R3 payload-durable fact
```

The top's legacy `p3_packed_write_issue_in` and
`p3_packed_write_terminal_in` remain tied inactive.  They are direct
compatibility/test ingress only and must not become a second production
durability path.  This is the correction to the older shorthand that called
"p3_packed_write" inert: the old *direct* carriers remain inert, while the
already-wired candidate path becomes reachable only after RTL3.9-A can make a
real P3 stage `COMPLETE`.

## Frozen behavior and ownership

- R3 alone selects one `COMPLETE` local P3 stage for the functional write
  baseline, emits exactly one write request followed by the stage's exact
  eight fragments, and owns acceptance of the terminal/durable state.
- R2/R1/registry/router retain their existing sole ownership of candidate
  transport, allocated association, transaction identity, and typed terminal
  delivery.  B1 creates no scheduler, queue, credit, or R1 service rule.
- `layer`, `stage_generation`, `transaction_group_tag`, `page_ref`, candidate
  id, registry-held transaction identity, and `last` retain the B0
  exact-match requirement.  A stale/mismatched terminal is ready-low and
  cannot make P3 durable.
- `p3_payload_durable_out` means only that the packed payload write reached
  its accepted terminal.  It is neither descriptor durability,
  `metadata_publish_commit`, visibility, nor a pending-to-packed authority
  handoff.
- The directed evidence holds `ready` low before accepting the candidate and
  verifies that the descriptor is stable.  It then checks all eight fragments,
  rejects a wrong candidate id, and accepts only the matching successful final
  terminal.

The precise production composition was already structurally present before
B1 (`R3 candidate -> delivery-context composition -> R2 -> R1 -> typed router
-> R3 delivery`).  RTL2.1b's existing write-path harness independently covers
that R2/R1 transport.  B1's new test makes the upstream functional trigger and
the R3 durable acceptance explicit, without adding a testbench bypass to the
top.  The historical RTL2.1b harness now explicitly sinks the two materializer
offers it intentionally does not consume; this is elaboration hygiene for that
hot-ingress-only harness, not a production-path tie-off or an owner change.

## Evidence boundary

This is a pure Chisel directed functional/protocol closure.  It makes no claim
about an HBM controller, HBM burst/address mapping, SRAM macro or port count,
clocking/CDC, cycle latency, throughput, deadlock freedom, area, energy, PPA,
numeric RTL, model/GPU behavior, or a new A4 DSE.  It does not activate
descriptor durability, publication, R6 authority transfer, source service, or
full inference.

## No-model validation

```bash
.venv/bin/python tools/validate_rtl3_9_b1_r3_packed_write_activation.py --help
.venv/bin/python tools/validate_rtl3_9_b1_r3_packed_write_activation.py
.venv/bin/pytest -q tests/test_rtl3_9_b1_r3_packed_write_activation.py
cd hardware/route_a/chisel
sbt -batch 'testOnly kvpress.routea.rtl3.RouteARTL39AMaterializationSpec'
sbt -batch 'testOnly kvpress.routea.rtl2.RouteA2_1bWritePathHarnessSpec'
```
