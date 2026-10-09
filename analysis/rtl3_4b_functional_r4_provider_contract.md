# RTL3.4-B — oracle-consistent functional R4 provider

**Status:** `implemented_functional_oracle_provider_pre_rtl3_5_partial_producer`.

RTL3.4-B replaces the former opaque R4 success/fault *decision* in the
functional verification path.  It does not implement an FP datapath in
Chisel.  Instead, it freezes a lossless Chisel accepted-packet egress and a
pure-software functional provider that evaluates only the already frozen
RTL3.3 oracle from those exact packet bytes.

```text
structurally accepted R4 header + sideband + 0/8 fragments
  -> route_a_merge_boundary complete accepted-packet egress
  -> route_a_functional_r4_merge_provider (pure software)
  -> existing per-consumer R4 success XOR numeric-fault carrier
  -> route_a_merge_boundary
  -> R6 group terminal aggregation from RTL3.4-A
```

The production composition top deliberately drains/discards the accepted-packet
egress with `ready` high and keeps its result inputs inactive.  Therefore this is a functional
testbench/reference realization boundary, not a production-top numeric-core
activation.

## Unique ownership and exact input rule

`route_a_merge_boundary` remains the sole structural packet acceptance owner.
Only after it accepts a header/sideband pair and either the frozen absent
header or all eight ordered value fragments does it emit one
`R4AcceptedPartialPacket`:

| Field | Source | Rule |
|---|---|---|
| transaction identity | accepted header | exact `(request_id, incarnation)`; request ID alone is insufficient |
| source instance | accepted sideband | exact source kind, coordinate, generation |
| consumer ID | accepted header and sideband | exact RTL3.4-A consumer association |
| header | accepted 128-bit header | retained without numerical reinterpretation by Chisel |
| value payload | accepted fragments | 4,096-bit `fragment[0]` at low bits through `fragment[7]` at high bits; absent is all zero |

The Decoupled egress is held stable under ready-low.  It blocks a following
packet until consumed, so a functional provider cannot silently lose an
accepted packet.  Its logical packet width and buffering are not an SRAM,
port, bandwidth, or timing selection.

The software provider owns no packet acceptance, source selection, or outward
terminal.  It stores at most the exact accepted canonical packets keyed by
`(transaction_identity, consumer_id)`, accepts one `R4MergeWork` from the
already accepted R6 work fact, and has only these outcomes:

- It inserts the frozen absent identity only for a source excluded by that
  work item's accepted source-presence mask.
- It invokes `DEFAULT_R4_FUNCTIONAL_PROFILE.merge_packets` in frozen
  `hot -> pending -> packed` order, then packs the 128 binary32 normalized
  lanes according to RTL3.3.
- Missing expected packet, stale identity, duplicate packet/work, or
  source/consumer association mismatch is fail-closed and produces no success.
- A numerically illegal but structurally accepted packet maps to
  `numeric_fault` with no normalized payload; it does not retry, substitute
  Full-KV, or alter pruning/admission/publication.

Any provider terminal must return through the existing RTL3.4-A
identity-plus-consumer success/fault carrier.  `route_a_merge_boundary` and R6
remain the sole owners of R4-to-R6 and group outward terminal behavior.

## Evidence and exclusions

The provider is a pure-software functional oracle/model, and the Chisel change
is a structural packet reassembly/egress assertion.  Together they establish
an explicit bridge from Chisel-accepted packet bits to the frozen numerical
reference.  They do **not** establish cross-language numeric equivalence,
final synthesizable FP/exp RTL, attention-MAC realization, latency, service
rate, queue depth, throughput, deadlock freedom, SRAM/HBM/controller/CDC,
area, energy, PPA, model/GPU accuracy, or a new A4 DSE.

RTL3.5 remains blocked on its separate query/position/RoPE and partial-producer
boundary.  This phase does not let hot/direct/S2 storage owners produce
attention partials.

## No-model verification

```bash
.venv/bin/python -m pytest -q \
  tests/test_route_a_merge_numeric_reference.py \
  tests/test_rtl3_3_r4_functional_profile.py \
  tests/test_rtl3_4b_functional_r4_provider.py
cd hardware/route_a/chisel
sbt -batch 'testOnly kvpress.routea.r4.RouteAMergeBoundarySpec'
```

The exact source/hash binding and command results are frozen in
[`rtl3_4b_functional_r4_provider_manifest.json`](rtl3_4b_functional_r4_provider_manifest.json).
