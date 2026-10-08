# RTL2.6.3 — publication-to-S2 verification association

**Status:** `implemented_test_only_association_adapter_not_production_bridge`.

RTL2.6.3 implements the otherwise missing association boundary between the
real R3 publication carriers and an attention-local S2 service identity.  It
requires all of the following before producing the existing `S2ServiceRequest`:

1. a `PublicationCommitObservation` from R3;
2. the matching R3 `pending -> packed` authority transition; and
3. a complete explicit verification association carrying request identity,
   page reference, group tag, valid-record count, S2 slot, and generation.

The adapter fail-closes a stale/wrong authority tag and any page/tag/record
mismatch.  Its ready-low assertion preserves the generated S2 service request.
It does not inspect private R3/R5 state, infer identity, generate
`PackedS2ReadWork`, select a source plan, or become a production R3/R5-to-S2
bridge.  `source_generation` is retained only in the explicit verification
association for a later composed S2 fill binding; it is not encoded in the
existing `S2ServiceRequest` carrier.

This is no-model, no-GPU, no-timing/PPA executable control evidence.  The next
composition step must attach this adapter to the real R3/R5 publication harness
and the RTL2.6.2a S2/source/R4/R6 harness in one instance; only then can the
required retained-transaction witness advance.
