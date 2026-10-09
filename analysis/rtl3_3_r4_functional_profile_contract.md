# RTL3.3 — R4 functional-realization profile and oracle binding

**Status:** `complete_functional_profile_oracle_binding_pre_rtl3_4`.

RTL3.3 freezes the functional provider profile that RTL3.4 must implement. It
does **not** replace the current verification-only R4 result stub, instantiate
`route_a_functional_r4_merge_provider`, or implement an exp/FP datapath. Its
purpose is to make the future provider's observable inputs, canonical ordering,
oracle, result representation, and numeric-fault disposition non-negotiable
before that behavior is added.

## Frozen functional profile

The selected profile is exactly the Gate-A Qwen anchor:

| Item | Frozen profile |
|---|---|
| source semantic order | `hot -> pending -> packed`; no arbitrary-reordering equivalence claim |
| source packet set | exactly one header/packet entry per canonical source; absent is the existing header-only `(-inf, +0, +0[128])` identity |
| consumers / merge instances | four consumer IDs `0..3`; one merge instance, encoded as `0` |
| present partial | binary32 `m`, binary32 `l`, 128 binary32 `o` lanes, eight ordered 64-B fragments |
| merge / normalization oracle | existing `kvpress/route_a_merge_numeric_reference.py`, canonical binary32 operation and A2 envelope `atol=1e-5`, `rtol=1e-4` |
| fault rule | empty set is an interface assertion; invalid/nonfinite/overflow or `l <= 0` is `numeric_fault`, with no normalized output, retry, fallback, or policy change |

For the future functional provider's successful `R4ResultStub.normalized_value`,
RTL3.3 additionally freezes an otherwise missing wire representation:

```text
normalized lane i (binary32, little endian) -> bits [32*i + 31 : 32*i]
i = 0..127; total = 4096 bits
```

This encoding applies to the future functional provider only. The existing
RTL2 verification stub's payload remains opaque test data; it is not
retroactively reclassified as a numeric implementation.

## Chisel and oracle binding

`RouteAMergeBoundary` remains a structural owner. It accepts the canonical
128-bit header/sideband pair and zero/eight ordered 512-bit value fragments,
then maps only a later matching success-XOR-fault terminal to R6. It does not
inspect binary32 finite values, evaluate the oracle, pack normalized output,
or turn packet errors into a terminal.

RTL3.3 records one exact shared profile fixture:

```text
m = 1.25f, l = 2.5f, source = hot, consumer = 2,
instance = 0, present = 1, fragment_count = 8
128-bit wire word = 0x0000000000000228402000003fa00000
```

The Python profile adapter decodes all three canonical packets, calls only the
existing R4 numeric reference in the frozen order, and packs/unpacks the
future success payload by the lane rule above. The Chisel directed test accepts
the exact fixture through the existing structural boundary and explicitly
states that it performs no arithmetic. Together these are an oracle/interface
binding, not a cross-language FP implementation equivalence proof.

## Owner and assumption split

| Role | Rule |
|---|---|
| source/partial producer (deferred RTL3.5) | supplies only accepted packet data and the explicit query/position association; it does not choose R4 order by storage ownership |
| `route_a_functional_r4_merge_provider` (deferred RTL3.4) | will be the sole numeric/oracle provider and emit exactly one matching success or numeric fault |
| `RouteAMergeBoundary` / R6 | retain packet commit, active merge, R6-facing terminal, and outward terminal ownership |
| environment assumption | a future functional provider receives only structurally accepted packets with their existing identity/consumer associations |
| DUT guarantee after RTL3.4 | no result before accepted nonempty merge; success XOR fault; fault has no normalized payload; R6 remains the only outward terminal consumer |

## Deliberate exclusions

RTL3.3 does not select an exp approximation, internal precision, accumulator,
FP unit, lane storage, pipeline, latency, service rate, attention MAC, or
source schedule. It does not bind a production top, R3/R5/S2 dataflow,
sidecar transport, query/RoPE provider, controller/CDC, SRAM/HBM macro, power,
area, timing, throughput, model/GPU workload, accuracy result, Full-KV
fallback, or new A4 DSE.

## No-model verification

```bash
.venv/bin/python -m pytest -q \
  tests/test_route_a_merge_numeric_reference.py \
  tests/test_rtl3_3_r4_functional_profile.py
cd hardware/route_a/chisel
sbt -batch 'testOnly kvpress.routea.r4.RouteAMergeBoundarySpec'
```

The first command checks the profile/oracle reference; the second checks only
the shared packet fixture at the structural Chisel boundary. Source hashes and
machine-readable limits are frozen in
[`rtl3_3_r4_functional_profile_manifest.json`](rtl3_3_r4_functional_profile_manifest.json).
