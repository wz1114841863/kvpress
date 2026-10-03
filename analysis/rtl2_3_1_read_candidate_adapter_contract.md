# RTL2.3.1 — producer-local read-candidate adapter

**Status:** implemented and directed tested.  This closure makes the
RTL2.3.0 descriptor actionable without activating a production read path.  It
adds `route_a_read_issue_candidate_adapter`, a state-free translation from an
immutable `ReadIssueDescriptor` to the already-frozen R2 `SourceCandidate`.
The adapter is tested in isolation and deliberately is **not** instantiated by
the production top.

## Narrow behavior

For one legal producer-provided descriptor, the adapter copies, without
decoding or selecting:

```text
delivery_context_ref, candidate_class,
arrival_ordinal, candidate_id, eligibility_snapshot,
transaction_identity, target_descriptor
```

It forms the pre-existing logical R1 read request exactly as:

```text
request_kind             = coreMemoryReadRequestCode
destination              = destination_endpoint
address_ref              = payload_handle_or_address
expected_fragment_count  = expected_fragment_count
fragment_index           = 0
last                     = false
data                     = 0
```

This is only construction of the existing candidate carrier.  It is not R2
acceptance, a request-ID allocation, a core-memory launch, a controller
command, a payload transfer, or evidence that an external request occurred.
The owning producer still supplies the existing ordinal/ID/predicate facts;
R2 remains the sole owner of FIFO order, credit, eligibility evaluation,
read rotation, and grant-on-R1-accept.

## Fail-closed ingress rule

The adapter exposes no candidate and applies no input `ready` for an issue
that has any of the following conditions:

- class is not one of `s2_full`, `s2_packed`, `direct_pending`, `pack_read`;
- `source_kind=hot` (hot has no core-memory read); 
- `valid_count=0` or `valid_count>64`;
- `expected_fragment_count=0`; or
- `pending_explicit_empty=true`.

These are source-interface legality checks only.  They do not choose a
scheduler policy, convert an empty source into a memory operation, prescribe a
timeout/retry, or alter the frozen pruning/admission/authority semantics.  A
future source owner must hold a legal descriptor stable while `candidate_out`
is valid and `ready` is low; the adapter contains the corresponding
ready-low stability assertion.

The full target-kind-to-class check remains owned by the existing
delivery-context registry when an allocation is eventually requested.  RTL2.3.1
does not allocate, bind, reuse, or release a context reference.

## Explicit non-activation

The production top continues to have no instance of this adapter and its typed
read output stays tied inactive.  Therefore this closure cannot:

- inject a read candidate into R2 or change the frozen
  `s2_fill -> direct_pending -> pack_read` rotation;
- allocate a delivery-context association or create an R1 outstanding request;
- deposit a response into P3/S2/direct, set S2 `READY`, or make a source
  deliverable;
- emit `request_accept`, `fragment_deliver`, or any new scoreboard event;
- change pending/packed authority, metadata publication, GQA completion, R4,
  fault terminal handling, retirement, reclaim, or Full-KV fallback behavior.

## Directed evidence

`RouteAReadIssueDescriptorSpec` covers both the complete immutable descriptor
mirror and the adapter.  The positive case checks exact propagation into the
R2 candidate/R1-read fields and ready-low holding.  Negative cases verify that
non-read class, hot source, zero count, and explicit-empty input fail closed
before candidate creation.

Run from `hardware/route_a/chisel`:

```bash
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch 'Test / compile'
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch \
  'testOnly kvpress.routea.rtl2.RouteAReadIssueDescriptorSpec'
```

Passing evidence is synthesizable interface/functional-control evidence only:
no model/GPU, cycle, latency, throughput, PPA, physical-memory, controller,
numeric RTL, deadlock-freedom, or new A4 DSE claim.

Recorded result: JSON parse and `git diff --check` preflight passed; `Test /
compile` passed; `RouteAReadIssueDescriptorSpec` passed 3/3, including the
`valid_count=65` fail-closed case.  The existing R2/top suites remain outside
this isolated adapter's activation boundary; the adapter has no production-top
instance and therefore cannot alter their active carrier graph.
