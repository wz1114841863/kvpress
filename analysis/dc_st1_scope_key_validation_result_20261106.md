# ST1 scope and key predicate validation — 2026-11-06

## Disposition

The next planned batch is complete at **contract review and source-predicate
replay** scope. It does not establish actual wrapper RTL equivalence.

`ST1-01` is reviewed: the current production caller enforces global bound
ordinal nonreuse; the reviewed generic contract does not establish that
condition as an obligation on every caller. `ST1-25` is checked at the source
predicate level: another bank's same ordinal can pass admission ready and
then fail the original journal assertion. A separate counterfactual overwrite
diagnostic exposes the predicted C.ready difference, including C.valid=0.

Therefore **do not implement the simple journal-only replacement in the
generic wrapper under the current unqualified compatibility requirement**.
This is a scope qualification failure, not evidence that all journal reuse is
impossible or that a legal production request has failed. Conditional reuse
remains a candidate for the actually bounded production contour; that contour
is not silently substituted for the generic interface.

No production Scala/RTL, testbench RTL, generated HDL, constraints, synthesis
scripts or frozen input was changed. No Chisel/Verilator build, native HDL
simulation, formal invocation or DC ran. All checks are local; RD2's source
and inputs are unchanged and no remote connection or tmux/process operation
was performed. The old ST1 plan/matrix and STORE P0 remain historical records.

## Contract ownership finding

| Authority | What it actually establishes | A-NR disposition |
|---|---|---|
| `rtl1_i2_admission_publication_contract.md:20` through `:33` | Ordinal/population describe a specific immutable publication group; R3 validates the matching live P3 group and rejects duplicates within its membership | Does not impose global ordinal uniqueness across all banks/groups for an entire reset epoch |
| `rtl3_9_a0_pending_payload_read_association_contract.md:37` through `:64` | Exact atomic binding association, immutable member identity, absent-binding packing path and stale/mismatch rejection | A duplicate cannot replace an existing binding; no explicit global journal-index namespace for all generic callers |
| `mr1b_direct_pending_cross_owner_contract_proposal.md:614` through `:674` | Fixed 64-entry reset-only journal justified by the real ingress admitting one group and never rearming before reset | Production-composition guarantee, not general multi-group caller coverage |
| `rtl_entry_interface_manifest.json`, `if_pending_payload_read_binding` | External pending owner supplies opaque binding on an accepted RETAIN and joins atomically | No declared global ordinal-nonreuse input obligation |
| `rtl_entry_assertion_matrix.json` and its verification contract | Existing safety/assumption separation; reviewed records contain no global journal-ordinal caller assumption | Cannot use these to relabel the new A-NR obligation as already accepted |
| `RouteAAdmissionPublicationIngressAdapter`, source `:1330` through `:1499` | One locked group, per-ordinal presence guard and StateDone with no return to collection until reset | Enforces A-NR for actual production wiring |
| `RouteAM2P3Wrapper`, source `:2686` through `:2713` | Bank-local admission guard plus a global duplicate-journal assertion after accepted admission | The assertion is not ready gating and is not a general caller guarantee |

This review does not decree that every assertion-violating raw sequence is
architecturally legal. It establishes a narrower result: the simple
replacement cannot be promoted to unconditional generic compatibility from
the currently reviewed authority. Neither changing the caller contract nor
adding a ready gate is part of this batch. A-NR must not be justified merely
by assuming the very DUT assertion whose coverage is in question.

## Reproducible checks and evidence tier

New checker: `tools/check_st1_journal_suffix_scope.py`.
It validates the pinned current source hash and extracts **19 actual Chisel
expressions**, including admission matching/ready, full-ordinal checked-work
legality/ready/valid, and the original duplicate-journal assertion. It
translates that limited expression vocabulary to Python predicates and rejects
unsupported syntax. It does not replace the production source or produce a
synthesis candidate.

The executable fixture prescribes RESERVED stage/header states and manually
applies the corresponding member/presence/suffix/journal writes. It does not
execute the real claim FSM, all wrapper state transitions, four-state HDL
lowering, global M selection, response/durability, or publication logic.
Independent read values are checked without introducing one shared read port;
this is still not a native simultaneous-port implementation proof.
Absent data are arbitrary chosen fixture values, never evidence that the RTL
registers reset to zero. Bank encodings 36..63 are excluded as unspecified in
this replay and remain a separate reference-definedness review.

```bash
python3 tools/check_st1_journal_suffix_scope.py --help
python3 tools/check_st1_journal_suffix_scope.py \
  --output-dir analysis/experiments/st1_scope_key_validation_20261106_r2
.venv/bin/pytest -q tests/test_st1_journal_suffix_scope.py
```

The command refuses an existing result root. Reproduction uses a new ID;
never overwrite r2. The accepted local result is
`analysis/experiments/st1_scope_key_validation_20261106_r2/report.json`, SHA-256
`b794be38269dad9b4877802d4353953a878b21949963ca5edf64f0e400f76acf`.
The smaller checker-development r1 output is retained and is superseded by r2.
Source baseline is `0aa850df0a0774ca937564d596828e49fa13ee6b`; checker and
regression source hashes are recorded in the JSON companion so the previously
uncommitted checker at execution is reproducibly identified.

## Key results

Four checker regressions pass. They verify multiline-source extraction and
that the audit detects deliberate test-only string mutations that add
C.valid gating to ready, add journal-presence gating to admission, or replace
the full ordinal guard with its low bits. They mutate only in-memory source
copies, never production files. This verifies checker sensitivity, not RTL.

The replay finishes 14 check groups: 13 source-predicate groups (including
one expected original-assertion violation) plus one explicitly counterfactual
post-assertion diagnostic. The source groups contain 11,820 recorded probes;
they are not 11,820 RTL tests or a formal exhaustive input proof.

| Check | Observed source-predicate result |
|---|---|
| All 36 x 64 addresses | 9,216 valid/sink-ready combinations match after accepted fixture writes; pre-edge presence rejects work |
| Independent same-bank and cross-bank reads | Separate requested ordinals give the same suffix views; no imposed M=C or single-bank rule in the check |
| Suffix integrity | Each of 80 suffix bits independently changed in work is rejected; high-bit opaque handles are retained |
| Member/stale integrity | Each of 64 reference bits changed, or stale stage generation, is rejected |
| C ordinal 0..127 | Original full-width guard rejects upper-half aliases |
| Tail counts 1, 2, 63, 64 | Last valid ordinal accepts and first invalid ordinal rejects |
| Atomic join | Absent context or authority accepts no member write |
| Full unbound capacity | 2,304 fixture member slots accept unbound admissions; none receives a binding or pending work permission |
| Cross-bank alias without binding | A journal record elsewhere cannot authorize an absent/unbound bank's C work |
| Claim mask clearing | Clearing bank binding presence rejects C while the old journal remains |
| Same-bank duplicate | Original bank membership ready rejects it |
| Different-bank same bound ordinal | Original local ready accepts; original journal assertion evaluates false |

For the negative case, bank A/ordinal 0 first has handle 17; bank B/ordinal 0
offers handle 34 with otherwise matching local admission facts. The checker
stops that prefix at the failed original assertion and does not commit it as
a legal trace. In a separately marked counterfactual calculation, replacing
only journal(0) with B's binding gives:

| Probe for A's original work, C.valid=0 | C.ready | issue.valid |
|---|---:|---:|
| independent suffix reference | 1 | 0 |
| naive journal view after overwrite | 0 | 0 |

This does not report a newly observed full-RTL failure. It makes the source
reason for the conditional domain executable and prevents a false universal
equivalence claim.

## Relationship to the 30-case plan

| Planned cases | What this batch closes | Remaining status |
|---|---|---|
| ST1-01 | Contract review and authority classification completed | Generic eligibility not established; no new assumption approved |
| ST1-03..12, 18, 20..21, 24..25 as relevant | Limited address/data/ready predicates and key negative prefix checked | Source-level evidence only; real-wrapper RTL cases NOT_RUN |
| ST1-02, 13..17, 19, 22..23, 26..28 | No new full reset/lookup/withdrawal/mixed-bank/publication/composition/width result | NOT_RUN at planned RTL tier |
| ST1-29..30 | No synthesis or cumulative integration | NOT_RUN |

The original matrix is not relabelled wholesale as PASS. In particular,
source-only independent read evaluation is not the concurrent actual-wrapper
test, and selected values do not prove all parameter widths. Full RTL and
composition checks are deferred because the required generic scope gate has
not closed; they would not repair a missing contract guarantee.

## Practical next boundary

Retain the current generic suffix backing. No generic ST1 RTL replacement or
DC is eligible from this batch. The completed result is a useful stop decision:
it avoids spending a long synthesis run on an unqualified representation.

Two genuinely different future choices remain: an explicitly reviewed
production-only storage specialization, or a generic realization that preserves
independent values on cross-bank collisions. Neither is automatically
authorized. A generic fallback must actually store displaced arbitrary suffix
values and account for its worst-case capacity, reads and timing; a tag or
additional ready gate alone is not a solution. The positive source checks
remain reusable evidence for a correctly scoped future candidate.

No mapped-area, timing, lint, PPA, zero external cost, speedup or hardware net
benefit follows. Local source/evidence hashes, checker tests, JSON parsing,
document links and git whitespace checks close this batch; RD2 is untouched.
