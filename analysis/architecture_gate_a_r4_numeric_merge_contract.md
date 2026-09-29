# Gate-A R4 — finite numeric merge closure

## Status and boundary

**Status:** `complete_pure_software_finite_numeric_merge_contract; pre_rtl_only`.

R4 closes the observable numeric boundary of the Route-A online-softmax merge
for the selected Qwen3-8B anchor. It freezes binary32 module-boundary fields,
canonical source order, normalization precondition, and fail-closed numeric
disposition. It does not select an exp approximation, accumulator precision,
pipeline/register placement, timing, throughput, storage macro, energy/PPA, or RTL.

R4 preserves A2 source order `hot -> pending -> packed` and A4.13.4 FP32
partial-state vocabulary. It creates no model/GPU execution, new A4 DSE,
numeric-quality/workload claim, arbitrary-reordering claim, or change to mask,
admission, FIFO, source ownership, GQA completion, or atomic publication.

## Selected finite anchor format

One Qwen-anchor partial belongs to one of four query-head consumers of the one
active GQA group. It contains binary32 `m`, binary32 `l`, and 128 binary32
weighted-value lanes `o[127:0]`: `(128 + 2) * 4 = 520 B` per partial and
2,080 B for the four preexisting logical partial states. This is an
interface/state count, not an RF/SRAM/spill or traffic/energy estimate.

The selected little-endian 128-bit logical packet header is:

```text
bits [ 31: 0] m_binary32
bits [ 63:32] l_binary32
bits [ 65:64] source_ordinal {hot=0, pending=1, packed=2}
bits [ 67:66] consumer_id[1:0]
bit  [    68] merge_instance_id = 0 for the selected one-group anchor
bit  [    69] partial_present
bits [ 73:70] value_fragment_count {0 when absent, 8 when present}
bits [127:74] reserved, written and checked as zero
```

For a present partial, `o[127:0]` follows in eight ordered 64-B fragments
(`o[0:15]` through `o[112:127]`, each lane little-endian binary32). For an
absent source, the header-only form has count zero and denotes exactly
`(-infinity, +0, +0[128])`. The packet shape uses R1's core-side fragment only
as a logical interface; it is neither an HBM burst nor a port/service-rate claim.

Only `consumer_id=0..3` and `merge_instance_id=0` are accepted. A non-anchor
design needs a separately reviewed parameter/profile rather than silently
widening this contract.

## Operation, comparison, and faults

Present partials require finite binary32 `m`, finite binary32 `l > 0`, and
finite binary32 `o` lanes. The canonical operation is unchanged:

```text
m = max(m_a, m_b)
l = exp(m_a - m) * l_a + exp(m_b - m) * l_b
o = exp(m_a - m) * o_a + exp(m_b - m) * o_b
```

The R4 reference applies IEEE binary32 round-to-nearest, ties to even, at each
observable merge result and normalized output lane. Host-precision mathematical
`exp` only defines the expected result: it selects neither an exp
microarchitecture nor arbitrary-implementation bitwise equivalence.

An exponent scale may underflow to `+0`. A present/output NaN, infinity,
`l <= 0`, or binary32 overflow is terminal `numeric_fault`: it produces no
normalized output and selects no retry, fallback, mask/admission change, or
context reuse. An entirely empty source set is an assertion failure, not zero
output. Normalization requires nonempty input and `l > 0`.

The executable reference compares canonical binary32 results to A2 lane by
lane. `m` must have identical binary32 bits; `l` and every `o` lane require:

```text
abs(observed - A2_reference) <= 1e-5 + 1e-4 * abs(A2_reference)
```

These constants reuse the hard FP32 same-mask envelope as an interface
conformance rule, not a measured future-RTL bound or relaxation of an A4 guard.
The reference has all-seven-subset, malformed/overflow/empty, and fixed-seed
random binary32 tests. It has no source-reordering mode; another order needs a
separate finite-precision validation and specification revision.

## Integration and evidence boundary

R4 consumes a consumer partial only after existing source/GQA ownership has
committed its update. It cannot release S2/direct-pending ownership or make a
source ready, published, or authoritative. Its output can satisfy an existing
merge dependency, while final producer/consumer ports and lifecycle wiring
remain R6 work.

`kvpress/route_a_merge_numeric_reference.py` and
`tests/test_route_a_merge_numeric_reference.py` are pure-software
architecture-contract evidence. They establish packet fields, binary32
operation, A2 relation, normalization guard, and fail-closed exceptions only.
They make no model/GPU, cycle/timing/throughput, HBM/controller, PPA, RTL,
accuracy, or new-A4-DSE claim.
