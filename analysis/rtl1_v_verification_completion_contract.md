# RTL1-V — assertion, fairness, and scoreboard verification completion

**Status:** `contract_frozen_implementation_in_progress`.

RTL1-V closes verification evidence intentionally left after RTL1-I0--I4. It
does not revise a Route-A architecture choice: it does not connect top-inert
P3/source/R4 producers, choose a numeric datapath, create a controller or
physical-memory decision, or establish timing, throughput, PPA, model, GPU,
or end-to-end correctness evidence.

## Owner assertion closure

R5 remains the only allocator/generation owner. Its assertion observes the
existing one-line reclaim terminal: a lane that becomes free with a nonzero
generation must have crossed that line's matching successful, durable R1
descriptor terminal while the existing R6 reclaim permit was active. The
permit is the existing session-wide quiescence fact; RTL1-V adds no per-page
quiescence table.

R6 remains the lifecycle association owner, not a copy of hot/pending/packed
storage. Its assertion therefore checks authority *linearization edges*:
arrival is `none -> hot`, maturity is `hot -> none` or `hot -> pending`, and
the sole R3 post-publication fact is `pending -> packed`. Complete per-token
`authoritative_count == 1` is checked by the Python architecture reference
from the same frozen event trace. P3, S2, and direct transport copies remain
excluded from authority.

## Fairness and scoreboard boundaries

The three progress records use finite testbench witnesses only: required
external completions, consumers, drains, and terminal paths are eventually
released after legal ready-low intervals. This is neither a timeout nor a
throughput/DUT guarantee.

`analysis/rtl1_v_scoreboard_event_schema.json` is the only vocabulary accepted
by the host-side adapter. It preserves identity, generation, authority, and
commit nesting, rejects unknown/malformed events, and calls frozen Python
references. It neither observes raw HBM bytes nor offers cycle-by-cycle RTL
equivalence, model execution, numeric arithmetic, or Full-KV fallback.

## Required evidence and disposition

RTL1-V completes only when it has: (1) the R5/R6 owner assertions and negative
directed tests, (2) a fixed-seed legal-stall R1→R2→R5/R6 composition, (3) an
adapter test for authority, reclaim, and finite-fair lifecycle traces, and
(4) updated manifest/SVA validation. PASS authorizes RTL2 production-dataflow
planning and its first control/event slice, not an HBM controller, numeric RTL,
timing, PPA, or speedup claim.
