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

## Required RTL2.6.1 closure

1. Bind the remaining ten events to their existing named owner carriers, with
   exact identity/generation fields and no internal-state inference.
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
