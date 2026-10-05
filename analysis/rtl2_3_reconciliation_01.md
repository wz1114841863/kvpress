# RTL2.3-R — active phase and scoreboard-event reconciliation

**Status:** `active_navigation_reconciled; no_behavioral_activation`.

This is a living navigation correction after the RTL2.3 completion audit. It
does not modify the historical RTL2.0 activation manifest, the v1.0
pre-behavior scoreboard schema, frozen Gate-A records, architecture semantics,
or Chisel behavior. Its purpose is to make the active phase contract agree with
the already implemented C1--C5 boundaries and with the required event order.

The machine-readable active phase overlay is
[`rtl2_scoreboard_event_phase_reconciliation_01.json`](rtl2_scoreboard_event_phase_reconciliation_01.json).
The historical v1.0 record remains
[`rtl2_scoreboard_event_schema.json`](rtl2_scoreboard_event_schema.json).

## Reconciled event order

The prior v1.0 schema is a valid historical pre-behavior binding, but its
future-phase labels predate the canonical RTL2 numbering reconciliation. The
active map is therefore:

| Event group | v1.0 future label | Active behavioral entry | Reason |
|---|---|---|---|
| `source_deliverable` | RTL2.4 | RTL2.3-C7 | A source owner may be observed only through the top-integrated adapter path; C7 emits no host-side packet record. |
| `consumer_partial_commit`, `source_release` | RTL2.4 | RTL2.3-C8 | Four matching R4 commits precede an owner release. |
| `merge_request` | RTL2.5 | RTL2.3-C8 | R6 emits it after exactly the planned releases; R4 result acceptance remains later. |
| `attention_terminal` | RTL2.5 | RTL2.4 | The verification-only R4 result/fault stub is the sole terminal producer. |
| `descriptor_invalidate`, `page_free`, `retire_ack` | RTL2.6 | RTL2.5 | They belong to active-state reset/fault/retirement/reclaim, before the RTL2.6 review. |

All records remain `not_emittable_until_named_behavioral_phase`. This is a
schedule correction, not permission to emit a new scoreboard event today.

## RTL2.3 completion sequence

RTL2.3 retains its canonical scope: **source service and multi-source
composition**. C1--C5 close preparation, endpoint witnesses, and structural
packet ingress only. They do not satisfy the parent phase by themselves.

The remaining active sequence is deliberately finite:

1. **RTL2.3-C6 — source-plan binder closure: complete.**
   [`rtl2_3_c6_source_plan_binder_contract.md`](rtl2_3_c6_source_plan_binder_contract.md)
   names the non-top producer of the immutable source declaration accepted by
   R6. It validates and binds a declared nonempty source set; it does not
   choose a scheduler, substitute a source, or manufacture a plan at the top.
2. **RTL2.3-C7 — source-service top integration: complete.**
   [`rtl2_3_c7_source_service_top_integration_contract.md`](rtl2_3_c7_source_service_top_integration_contract.md)
   instantiates and wires the existing packet adapter from the accepted plan
   copy and exact source-owner availability observations. The top remains
   composition-only and packet ingress remains fail-closed.
3. **RTL2.3-C8 — four-consumer completion.** Exercise all seven nonempty masks
   through R4 commit demultiplexing, one generation-bearing owner release per
   present source, and the consequent R6 `merge_request`.
4. **RTL2.3-C9 — live endpoint composition.** Replace isolated C2/C3/C4
   endpoint witnesses with one authorized top composition path. Opaque
   verification packet fragments remain explicitly non-numeric until a later
   numerical realization gate.

RTL2.3 may pass only as `control_protocol_complete` after C6--C9. It must not
be called production attention, numeric correctness, or end-to-end Route-A
dataflow correctness. RTL2.4 begins only after that point and closes the
replaceable R4 result/fault-stub terminal path.

## Validation and evidence boundary

```bash
python3 -m json.tool analysis/rtl2_scoreboard_event_phase_reconciliation_01.json >/dev/null
git diff --check
```

This record and its JSON overlay are documentation/provenance navigation only:
no model/GPU, new A4 DSE, RTL behavior, numerical datapath, cycle/timing,
throughput, physical-memory, or PPA claim is made.
