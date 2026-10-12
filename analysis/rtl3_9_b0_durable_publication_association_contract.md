# RTL3.9-B0 — durable-write/publication activation association audit

**Status:** `complete_pre_activation_association_audit`.

RTL3.9-B0 closes the identity and owner boundary required before activating
the existing P3 packed-write, descriptor-durability, and publication paths.
It changes no Chisel behavior and keeps the top's `p3_packed_write_issue` and
`p3_packed_write_terminal` carriers inert.

## Frozen association chain

```text
R3 stage: layer + stage_generation + group_tag + page_ref + KV head
  -> R3 packed-write candidate / registry-held delivery descriptor
  -> R2/R1 write request and matching typed terminal
  -> R3 payload-durable fact

same stage/page/tag
  + R5 descriptor-durability prerequisite
  -> R3 sole metadata_publish_commit candidate
  -> R5 visibility acknowledgement
  -> R6 sole pending -> packed authority transition
```

Owners are fixed as follows:

- R3 owns P3 state, packed-write candidate, durable-state acceptance, private
  M2 group, publication candidate, and the only post-publication authority
  transition it emits.
- The R2/R1/registry/typed-router chain owns candidate selection, transaction
  identity, request/response association, and typed terminal delivery.
- R5 owns page allocation, descriptor maintenance and visibility facts.
- R6 accepts the already-associated pending-to-packed transition; it neither
  initiates publication nor creates an alternative authority edge.
- The top only connects these named carriers and must not manufacture an
  issue, terminal, durability indication, descriptor prerequisite, publish
  acknowledgement, or authority transition.

## Mandatory exact-match checks for B1 onward

Every active path must preserve `layer`, `stage_generation`,
`transaction_group_tag`, and `page_ref`; the R3 packed-write terminal also
must match the registry-held write identity and last-fragment semantics.
Descriptor prerequisite must match the same stage/page/tag and required
descriptor-operation mask. A stale or mismatched fact is ready-low and cannot
make payload durable, descriptor durable, publication-visible, or packed
authoritative. Only the single metadata publication boundary may hand off
pending authority to packed authority.

## Disposition

B0 authorizes only RTL3.9-B1's narrow activation of the existing R3 packed
write path. It does not authorize a new scheduler, queue depth, R1/HBM
controller, address mapping, macro/port choice, numeric implementation,
timing, throughput, area, energy, PPA, model/GPU experiment, or a new A4 DSE.

## No-model validation

```bash
.venv/bin/python tools/validate_rtl3_9_b0_durable_publication_association.py --help
.venv/bin/python tools/validate_rtl3_9_b0_durable_publication_association.py
.venv/bin/pytest -q tests/test_rtl3_9_b0_durable_publication_association.py
```
