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
It intentionally does not claim Chisel event emission: two records require a
prior accepted R2/R1 association that is absent from a bare R1 carrier.

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
