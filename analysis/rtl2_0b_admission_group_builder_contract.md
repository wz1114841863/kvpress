# RTL2.0b — Retained admission-group builder

**Status:** `interface_owner_closed; behavioral_group_builder_pending`.

This closure refines the reviewed admission-publication ingress amendment into
a finite protocol owner.  It is not a simple fanout: it owns one transient,
immutable group-assembly association, then sequences R5 allocation, R3 P3
claim, claim acknowledgement, and exact member relay.  It owns no authority,
payload residency, R2/R1 transaction, metadata publication, allocator, or P3
stage state.

The authoritative machine-readable record is
[`rtl2_0b_admission_group_builder_manifest.json`](rtl2_0b_admission_group_builder_manifest.json).

The one-packer anchor permits at most one active group with at most 64 members.
This is the existing logical P3 group bound, not a physical FIFO/macro choice.
The existing narrow `P3Claim.owner` field is fixed to local reservation label
zero for this one-packer anchor.  It is expressly not a request ID, physical
address, scheduler decision, or authority owner.

```text
R6 exact RETAIN context + hot->pending event
  -> assemble every ordinal 0..valid_records-1
  -> R5 allocation
  -> matching page_ref
  -> R3 P3 claim
  -> matching stage_generation acknowledgement
  -> relay each original R6 context/authority pair exactly once to R3
```

Non-contiguous `entry_id` values are retained verbatim; first-entry-plus-count
span reconstruction is forbidden.  A partial group, mismatch, fault, or reset
has no P3 claim, R1 work, visible descriptor, publication, or packed authority.

This closure does not create the child or activate Chisel behavior.  RTL2.1a
may add the reviewed protocol-only child and wire the existing R6/R5/R3
carriers, but must first use the separately frozen RTL2.0a payload contract.

Validation:

```bash
.venv/bin/python tools/validate_rtl2_admission_group_builder_manifest.py --help
.venv/bin/python -m pytest tests/test_rtl2_admission_group_builder_manifest.py -q
```
