# RTL2 phase numbering reconciliation

**Status:** active navigation correction; no architecture or RTL behavior is
changed by this record.

Early RTL2 navigation used `RTL2.3` for the P3/S2 functional-storage
prerequisite even though the RTL2.2 delivery plan retained two following
substeps.  The canonical active numbering is now:

| Canonical stage | Scope | Prior active label, if any |
|---|---|---|
| RTL2.2.0 | delivery provenance/interface reconciliation | unchanged |
| RTL2.2.1 | registry allocation/reuse | unchanged |
| RTL2.2.2 | typed write-terminal routing | unchanged |
| RTL2.2.3 | replaceable P3/S2 functional-storage prerequisite | `RTL2.3` |
| RTL2.2.4 | typed read-delivery closure | newly restored delivery substep |
| RTL2.3 | source service and multi-source composition | prior planned `RTL2.4` |
| RTL2.4 | R4 replaceable result-stub activation | prior planned `RTL2.5` |
| RTL2.5 | active-state reset, fault, retirement, reclaim | prior planned `RTL2.6` |
| RTL2.6 | RTL2 completion/integration review | prior unnumbered completion review |

## RTL2.3-R active event-label reconciliation

[`rtl2_3_reconciliation_01.md`](rtl2_3_reconciliation_01.md) records the
first post-numbering active navigation overlay. It does not rewrite the
historical RTL2.0 activation manifest or v1.0 scoreboard schema. The active
completion order is `RTL2.3-C6..C9 -> RTL2.4 terminal stub -> RTL2.5
reset/reclaim -> RTL2.6 review`; the matching event labels are in
[`rtl2_scoreboard_event_phase_reconciliation_01.json`](rtl2_scoreboard_event_phase_reconciliation_01.json).

This clarification is necessary because a source release must precede the R6
merge request, an R4 terminal follows a merge request, and reclaim facts are
exercised before—not during—the final completion review. No event becomes
emittable merely by this navigation correction.

Historical Gate/RTL2.0 manifests are provenance records and are not rewritten.
Their former future-phase strings must be read through this table; they do not
authorize behavior beyond their original contract.  The active navigation is
[`rtl2_phase_contract.md`](rtl2_phase_contract.md).
