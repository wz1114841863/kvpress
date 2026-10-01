# Gate-RTL0.4 — Python scoreboard-oracle closure

**Status:** `complete_non_implementational_scoreboard_oracle_binding; rtl1_v_subset_event_adapter_complete`.

`rtl_entry_scoreboard_oracle_manifest.json` binds every RTL0.3 property to one
existing Python oracle and its event-level observable state.  The testbench
adapter must present the same accepted transaction events and compare only the
listed observables.  It may translate bundle representation, but may not alter
identity/generation, source order, ownership, authority, commit nesting,
failure disposition, or fairness assumptions.

The existing references remain authoritative: A2 architecture for authority/S2,
R1 memory for identity/reset, R2 for FIFO/credit, R3 for M2/P3, R4 for binary32
packet/fault relation, R5 for page reclaim, R6 for terminal/retirement, and
cross-closure for the shared publication nesting.  Python host arithmetic and
containers are golden semantic references only; they are not RTL datapaths,
microarchitectures, proof engines, or performance models.

Every RTL0.3 record has exactly one binding. RTL1-V's separate frozen event
schema and host-side adapter execute only its authority/reclaim/lifecycle
subset; the inventory registry remains the source of truth for every other
future testbench mapping. Progress bindings consume only a
finite fair event stimulus described by their matrix assumption; they do not
assert an unconstrained environment, a cycle deadline, or throughput.
