# RTL2.5.1 — destructive-reset active-state closure

**Status:** `complete_directed_reset_epoch_evidence; fault_retirement_reclaim_pending`.

## Scope

RTL2.5.1 exercises the destructive-reset behavior already owned by R1, R5,
S2/direct source wrappers, and the composed top-level R6 init boundary.  It
does not add a reset protocol, controller action, epoch-width choice, event
emitter, source scheduler, or production ingress.

The directed reset-epoch witness covers the following live local states:

| Owner / state before reset | Post-reset fact injected or checked | Required result |
|---|---|---|
| R1 live read identity | Delayed matching external response | R1 consumes it externally, produces no core response, and accepts no new request until a fresh `init_ack`. |
| R5 allocated and published page | Old allocation / descriptor-maintenance / visibility facts | R5 blocks them until renewed `mem_init_done`; after re-init it can allocate a new page without preserving the old local association. |
| S2 active fill association | Old payload/fill-open identity and generation | Slot returns to EMPTY; old facts cannot deposit or reopen the new association. |
| direct-pending active association | Old terminal identity/generation | Endpoint becomes inactive; old terminal cannot become deliverable or release a source after re-init. |
| composed R1/R3/R5/R6 initialization state | Session start after destructive reset | Top blocks start and core requests until a new R1 epoch acknowledgement and fresh init collection complete. |

The existing RTL2.4.2 R4--R6 harness separately covers reset after an accepted
R4 result-stub scenario, with no outward terminal.  RTL2.5.1 does not alter
that terminal contract.

## Frozen reset consequences

`destructive_reset` invalidates local reachability only.  It does not erase
HBM bytes, make a stale response authoritative, transfer authority, publish
metadata, complete a source, issue a descriptor invalidation, free a page, or
acknowledge retirement.  R1's external `init_ack` remains the only reset-epoch
release; ordinary responses are not an initialization acknowledgement.

An old identity/generation is never made safe merely because the finite local
counter begins again after reset.  It must also match a currently live owner
association created after the new initialization boundary.  This preserves the
frozen fail-closed rule for stale R1 responses, S2/direct source facts, and R5
descriptor facts without changing A3 identity/generation parameters.

## Evidence and boundary

`RouteAResetEpochIntegrationSpec` is deterministic no-model ChiselSim
evidence.  It uses one reset pulse for each named active local state, then
explicitly attempts the corresponding old fact.  It is not a proof that every
possible multi-owner interleaving is reset-safe, nor a formal proof of stale
HBM suppression, deadlock freedom, latency, throughput, area, energy, PPA,
numeric correctness, full retirement/reclaim behavior, or a new A4 DSE.

The next closure is RTL2.5.2 terminal-fault behavior.  `descriptor_invalidate`,
`page_free`, and `retire_ack` remain declared-only scoreboard targets until
their named behavioral substeps bind an accepted owner-local carrier.
