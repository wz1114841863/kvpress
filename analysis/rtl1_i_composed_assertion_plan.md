# RTL1-I — composed assertion plan

**Status:** `rtl1_i0_planning_frozen; no_composed_rtl_assertion_bound`.

This plan refines only the cross-owner observation needed to bind existing
assertion records. It does not replace their frozen owner, introduce a second
authority table, define an SVA proof depth, or claim formal/RTL correctness.

| Existing record | Owner remains | I0 composition boundary | Later proof obligation | Environment assumption |
|---|---|---|---|---|
| `a_metadata_publish_commit` | R3/M2/P3 | group membership ledger and R3 commit observation | every member observation derives from exactly one completed atomic publication | none |
| `a_authority_conservation` | R6 lifecycle | hot maturity, R3 member observations, and R5 visibility | each retained entry is one of hot/pending/packed; P3/S2/direct are transient | none |
| `a_gqa_release` | S2 wrapper | source-instance sideband through R4 commit | release has four distinct current-generation consumer commits | none |
| `a_numeric_fault_consumer` | R6 lifecycle | source releases -> merge-ready -> R4 terminal | numeric fault has one matching outward terminal only after source completion | none |
| `a_reset_stale_exclusion` | R1 core-memory wrapper | external init acknowledgement and generation-bearing delivery context | pre-reset/old-generation response has no reachable effect | adapter suppresses/drains old responses before init acknowledgement |
| `a_descriptor_invalidate_before_free` | R5 page manager | R6 global drain -> R5 invalidate -> R2/R1 terminal | free/generation advance follows durable invalidation and quiescence | external descriptor completion eventually returns for progress only |
| `a_global_retirement_membership` | R6 lifecycle | named component drain producers/status collector | retire ack implies all eight live predicates are empty | each legal external completion/eventually-ready consumer eventually completes |
| `p_accepted_to_terminal` | R6 lifecycle | source-plan/release/merge sequence | accepted attention reaches exactly one terminal under fairness | accepted external request and consumer eventually complete |
| `p_retire_to_ack` | R6 lifecycle | drain producers and R5 reclaim | retire reaches matching acknowledgement under fairness | all required drain/invalidation completions eventually arrive |
| `p_credit_return` | R2 arbiter | delivery context and publication/reclaim terminal routing | reserved logical credit returns once on the terminal path | bound request eventually terminalizes |

The composed monitor is verification-only. It consumes immutable event
observations and may retain testbench/reference bookkeeping; it is not a DUT
storage owner and cannot authorize a source, page, or publication.
