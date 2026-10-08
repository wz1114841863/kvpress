# RTL2.6 — completion / integration review

**Entry-audit status:** `incomplete_scoreboard_and_transaction_witness`.

RTL2.6 is a review gate, not permission to conceal separate unit witnesses as
one production transaction. The immutable event schema names fourteen events.
At entry, only four have a real testbench binding: `attention_terminal`,
`descriptor_invalidate`, `page_free`, and `retire_ack`. The remaining ten are
still schema-only, so the review cannot consume an architectural event trace
covering the required retained path.

The current top also retains explicitly named verification ingress for R3
pack-read, direct-pending, S2 fill/read, and S2 sidecar facts. These are owned
and justified verification boundaries rather than unowned production carriers;
they must remain explicit until a separately authorized producer realization.

## RTL2.6.1 result and required RTL2.6.2 closure

RTL2.6.1 has now frozen the exact no-default field provenance for the ten
schema-only records in
[`rtl2_6_1_event_binding_contract.md`](rtl2_6_1_event_binding_contract.md).

### RTL2.6.2a progress

[`rtl2_6_2_composed_packed_source_harness_contract.md`](rtl2_6_2_composed_packed_source_harness_contract.md)
now closes a narrow same-instance S2 `READY` through packed source release,
R6 merge request, and R4/R6 numeric-fault terminal path.  Its explicit
verification fill/packet ingress does not constitute a production
R3/R5-publication-to-S2 bridge; therefore this review remains incomplete.

### RTL2.6.3 progress

[`rtl2_6_3_publication_s2_association_contract.md`](rtl2_6_3_publication_s2_association_contract.md)
now supplies the explicit test-only association needed to join a real R3
publication/authority pair to S2 service identity. Its page/tag/record and
authority checks are fail-closed, but it remains deliberately outside the
production top until a separately authorized realization is selected.

### RTL2.6.4 progress

[`rtl2_6_4_publication_to_terminal_composition_contract.md`](rtl2_6_4_publication_to_terminal_composition_contract.md)
uses that association in one Chisel instance: real publication reaches real S2
`READY`, four commits, source release, R6 merge, and one R4/R6 fault terminal.
It is a partial retained witness only: retirement/reclaim, success, event
capture/replay, and stale/stall full-composition branches remain open.
It intentionally does not claim Chisel event emission: two records require a
prior accepted R2/R1 association that is absent from a bare R1 carrier.

## RTL2.6 work breakdown and completion criterion

The original RTL2.6 plan named two implementation actions after the entry
audit: RTL2.6.1 field provenance and RTL2.6.2 one composed retained
transaction.  The latter was necessarily decomposed after implementation
revealed the publication-to-S2 identity gap:

| Label | Scope | Status | Does not establish |
|---|---|---|---|
| RTL2.6.1 | exact no-default field provenance | complete | Chisel event capture |
| RTL2.6.2a | S2/source/R4/R6 fault-terminal slice | complete | publication or retirement |
| RTL2.6.3 | publication-to-S2 verification association | complete | production bridge |
| RTL2.6.4 | publication-to-fault-terminal partial witness | complete | real read path, reclaim, replay |
| RTL2.6.5 | full retained-transaction and scoreboard witness | active | production-top/PPA/numeric realization |

RTL2.6.2a through RTL2.6.4 are therefore implementation sub-slices of the
original RTL2.6.2 objective, not additional architecture/DSE gates.

### RTL2.6.5 required closure

RTL2.6.5 is ordered internally to keep every remaining gap explicit:

1. **RTL2.6.5a — read-path composition.**
   - **RTL2.6.5a.1 — packed-S2 read:** complete.
     [`rtl2_6_5a_packed_s2_read_composition_contract.md`](rtl2_6_5a_packed_s2_read_composition_contract.md)
     replaces direct S2 payload injection with the existing typed packed-S2
     R2/R1 endpoint path.
   - **RTL2.6.5a.2 — R3 pack-read to P3:** complete.
     [`rtl2_6_5a2_r3_pack_read_p3_composition_contract.md`](rtl2_6_5a2_r3_pack_read_p3_composition_contract.md)
     composes the existing R3 `pack_read -> R2/R1 -> P3` path with its later
     packed write, descriptor prerequisite, and publication path in one R3
     instance. A response deposits only into its matching owner; stale and
     fault responses do not deposit. The bridge preserves a single context
     across a write request and its data carriers; it does not change R2
     arbitration or choose a member issue schedule.
2. **RTL2.6.5b — terminal-to-reclaim composition:** complete.
   [`rtl2_6_5b_terminal_reclaim_composition_contract.md`](rtl2_6_5b_terminal_reclaim_composition_contract.md)
   composes an accepted real R6 attention terminal, an explicit matching
   environment retire association, R6 global drain/permit, and the real
   R5->R2->R1 durable invalidation path to `retire_ack`. A mismatched retire
   is rejected and a reclaim terminal fault leaves retirement incomplete.
3. **RTL2.6.5c — event capture and oracle replay.** Capture all fourteen
   immutable-schema records solely from declared accepted carriers, then replay
   the trace through the Python scoreboard/oracles. Add one success, one fault,
   one stale-response, and one bounded legal ready-low case.
4. **RTL2.6.5d — completion review.** Re-run the entry audit only after
   2.6.5a--c pass. This is the sole point at which the review may evaluate a
   `rtl2_production_transaction_dataflow_complete` disposition.

None of these sub-slices authorizes a production R3/R5-to-S2 bridge, a
different scheduler/admission policy, numeric realization, controller/macro
selection, timing/PPA, model/GPU work, or a new A4 DSE.

1. Attach each declared field association to real owner-carrier handshakes in
   one test-only observation adapter; no field may be inferred from private
   owner state or supplied by a default.
2. Compose one no-model harness using real existing owners for the sequence
   `RETAIN -> pending -> packed -> packed-read/S2 READY -> four commits -> R4
   stub terminal -> retire -> reclaim -> retire_ack`.
3. Replay that captured event trace through the Python scoreboard/oracle; add
   a representative stale response, fault, and legal ready-low branch.
4. Re-run this review. Only then may its disposition become
   `rtl2_production_transaction_dataflow_complete`.

No numeric merge, physical HBM/SRAM/controller, scheduler change, profiling,
frequency, timing, area, energy, PPA, model/GPU, or new A4 DSE is authorized
by this entry audit.
