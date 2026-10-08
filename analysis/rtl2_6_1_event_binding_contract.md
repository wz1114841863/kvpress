# RTL2.6.1 — event field-provenance binding

**Status:** `field_provenance_contract_closed_chisel_capture_pending`.

RTL2.6.1 freezes the exact owner/carrier and field association for the ten
event records that were still schema-only at the RTL2.6 entry audit. It does
not modify the immutable RTL2 event schema and does not claim that the ten
records are now emitted by Chisel.

Two records require explicit multi-carrier observation association:

- `request_accept` must retain R2's candidate class and delivery-context
  association together with the accepted R1 request identity; a bare
  `CoreMemoryRequest` cannot supply those fields.
- `write_commit` must retain the prior accepted write association through its
  terminal; a bare R1 response cannot reconstruct operation or context.

`metadata_publish_commit` is likewise a post-commit association of the
existing R3 commit/member/acknowledgement carriers. These are named,
accepted-carrier associations, never reads of private owner state and never
field defaults.

The machine-readable manifest provides one provenance entry for every schema
field. The Python adapter accepts only a complete, explicitly captured field
set; it cannot infer omitted fields. This is preparatory executable contract
evidence for RTL2.6.2, not a waveform capture or an RTL event-emission claim.

## Required RTL2.6.2 follow-on

Instantiate a test-only observation adapter in the composed harness, attach
the listed associations to real owner-carrier handshakes, and show ready-low
stability plus stale/fault fail-closed behavior. Only then may the phase
overlay mark these records as `bound_and_emittable`; the RTL2.6 entry audit
must remain incomplete until the single full transaction is captured.

No source scheduling, physical-memory realization, numeric implementation,
timing, performance, model/GPU, or A4 DSE claim is added.
