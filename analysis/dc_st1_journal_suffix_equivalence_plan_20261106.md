# ST1 journal-suffix reuse: equivalence domain and verification plan — 2026-11-06

## Decision and scope

This planning batch follows
[`dc_compact_store_p0_audit_20261106.md`](dc_compact_store_p0_audit_20261106.md)
at source revision `27c4beb9bd1f03809571f79bbd8667f9619d9d1c`.
It changes documentation only, performs no remote access and leaves RD2's
source, frozen inputs, tmux and run untouched. No candidate RTL, test harness,
emission, simulator build, formal invocation or synthesis is implemented/run.

**ST1 has a conditional generic-wrapper equivalence argument, not an
unconditional arbitrary-input equivalence result.** Within reset-reachable
histories in which accepted bound ordinals never reuse a journal slot,
R3's existing journal can supply both independent suffix readers without
changing logical concurrency, cycles or handshake equations. The one-group
production composition enforces that condition. The standalone wrapper only
asserts it; it does not reject every violating offer in hardware.

Therefore the unqualified generic-compatibility gate remains open. A future
implementation must first establish that its comparison domain covers the
required generic contract, without converting an unproved DUT assertion into
an environment assumption. Production-only testing is insufficient. If all
raw port histories, including continued operation after the duplicate-slot
assertion fails, are required, the simple journal-only replacement is rejected.

The concrete verification cases and status are in
[`dc_st1_journal_suffix_validation_matrix_20261106.csv`](dc_st1_journal_suffix_validation_matrix_20261106.csv).
Source checks/hashes and the reduced storage-equation check are in
[`dc_st1_journal_suffix_plan_evidence_20261106.json`](dc_st1_journal_suffix_plan_evidence_20261106.json).

## Candidate change being evaluated, not implemented

Only two reads currently consume membershipPayloadBindings:

| Consumer | Current address | Candidate read-only view | Required concurrency |
|---|---|---|---|
| M, materialized work | candidate layer / candidate ordinal | suffix of reconciliationBindings(candidate ordinal) | combinational, selected independently of C |
| C, checked external work | work layer / work ordinal[5:0] | suffix of reconciliationBindings(work ordinal[5:0]) | combinational even when work.valid is low |

Each suffix is transaction request/incarnation, full opaque payload handle,
source generation and destination. Width is `5 + addressRefWidth +
sourceGenerationWidth + destinationWidth`, 80 bits in fair-v1. The candidate
retains both full-width 64-bit values wherever required; no value truncation,
new address map, memory macro or allocation policy is proposed.

Keep the complete 36 x 64 member table and both per-bank presence masks,
headers, RD1 M/S/O reader, materializer selectors, C/F/B validation, publication,
R6 handoff and journal state. The candidate would remove only the separate
suffix data array and its four field writes. Both journal reads would be
ordinary independent combinational selections, not one arbitrated memory port.
The journal remains owned by R3. Its existing full-binding write, persistent
presence, transitioned bit, lookup bypass and withdrawal are unchanged.

Do not add journalPresent/layer-match tests to ready, skip C validation,
tie C to M internally, share a port by fire/ready, add a pipeline, or clear a
journal record early. Those are different changes with different semantics.

## Exact comparison domains

### D-G: conditional generic domain

Use the original wrapper as the reference, not the production loopback.
Within each destructive-reset epoch require:

1. The reference's existing protocol/range obligations, including the R3
   contract's layer range 0..35. All ordinary stale/mismatched/unbound inputs
   whose response is defined by the reference remain part of the comparison.
2. **A-NR:** no accepted admission with a binding uses an ordinal previously
   accepted with a binding in that epoch. This is the exact global condition
   checked by `assert(!reconciliationPresent(ordinal))` at source line 2711.
3. Reset-reachable state; no equality is assumed for uninitialized data whose
   presence is false. Both designs see identical input and ready sequences.

D-G does NOT impose one layer, one group, M=C, constant identity/generation/
destination, one reader per cycle, ordered admission arrival, or a new fairness
assumption. Bound members in different banks with distinct ordinals remain
allowed. Unbound packing may populate the full 36 x 64 member capacity and
may use ordinals also present in another bank's journal. C/F/B remain
independently driven, including mismatches and valid-low probes.

A-NR is explicit because the source assertion is NOT a ready guard or, by
itself, proof of an environment obligation. The B2c contract justifies the
reset-only journal with the actual one-group production ingress. It does not
establish an unrestricted multi-group bound-admission interface. Before a
generic acceptance label, classify A-NR against the intended existing wrapper
contract. Do not silently broaden its meaning or rewrite the historical
contract. Until that classification and RTL checks close, D-G is conditional.

The complete 7-bit C ordinal space must be tested. Values 64..127 must retain
the original full-width `< stageValidRecords` rejection; low-six-bit journal
indexing cannot replace that guard. For layer encodings 36..63, first inspect
the reference's definedness and generated lowering: do not invent a ready-low
guarantee for an out-of-range dynamic Vec read or mask an observable reference
difference. Any defined reference control behavior must match. An unspecified
case is recorded as such, with its contract source, not counted as a pass.

### D-P: actual production composition

The real ingress locks layer/head/tag/count, accepts each ordinal once, relays
each member once and finishes in StateDone until reset. Every relayed member
has a matching binding. Together with the real top's exclusive claim/admission
wiring, this establishes A-NR without a new hardware gate. Its source induction
is already recorded in STORE P0; compositional RTL verification is still due.

D-P supports a separate production comparison, but cannot replace D-G or be
used to serialize generic readers, remove generic unbound capacity, or claim
continuous multi-group/model-portable operation. ST1's preferred scope remains
generic under established existing obligations, not a new production-only
specialization hidden inside the wrapper.

### D-R: unrestricted raw interface histories

A short counterexample prevents an unconditional claim:

1. Reserve bank A and bank B, both with an available ordinal o.
2. Accept a matched binding with suffix X at (A,o).
3. Accept a different matched binding with suffix Y at (B,o).
4. Continue driving checked work for (A,o) with suffix X.

The reference's local admission ready checks can accept step 3; its duplicate
journal assertion then fails. If that assertion is ignored, suffix(A,o) is
still X while journal(o) is Y. With the other legal-work predicates and sink
ready true, reference C.ready is true and the naive shared C.ready is false,
even with C.valid low. A held M offer can likewise expose the changed value.
Adding a journal owner-layer test detects a collision but cannot recover X.
Adding ready-low at step 3 changes the handshake that the reference accepted.
Neither repairs arbitrary-input equivalence of the simple replacement.

Negative verification must observe the original assertion and accepted prefix;
it must not disable the assertion and count post-failure behavior as legal,
or gate away that prefix to manufacture equivalence. D-R is a counterexample
domain, not accepted ST1 coverage.

## Conditional storage relation and induction

For bank b and ordinal o, let Q be membershipPayloadBindingPresent, S the
reference suffix array, P the journal presence and J the full journal record.
Under A-NR, the relation to establish is:

```text
Q[b,o] => P[o]
          && J[o].layer == b
          && J[o].group_member_ordinal == o
          && S[b,o] == suffix(J[o])
```

This relation is stronger than needed because Q can remain set after its
member stops being readable. It is still preserved in A-NR histories:

- Reset clears Q/P; data need not be initialized or equal.
- An accepted bound admission writes S and the full J from exactly the same
  binding on the same edge, and sets Q/P. A-NR means it cannot overwrite J
  backing another retained Q bit.
- A claim clears the claimed bank's Q. Unbound admission does not write S/J.
  Existing observation/fault/status paths do not overwrite J. Publication and
  retirement cannot evict J. Reset begins a new independent epoch.
- A same-bank claim and accepted admission cannot both target that bank in
  a legal pre-edge state: claim requires EMPTY, admission requires a live
  nonempty stage. Different-bank events can remain concurrent.

M.valid requires an actual member and binding-presence bit, so its selected
suffix is equal on every valid cycle. C legality includes the SAME bank's
member and binding presence. When those predicates are true, the relation
gives equal data for all four comparisons; when a required presence predicate
is false, C is rejected regardless of suffix bits. Thus C.ready and issue.valid
remain equal in defined cases, including C.valid=0. The full ordinal and stage
generation guards remain unchanged.

Reads see pre-edge J.Q, just as S.Q before. A new admission becomes visible
after the edge through existing presence; add no M/C write-through bypass.
The journal's existing same-cycle lookup bypass is different and stays intact.
Equal C.ready and M valid/data preserve the existing acceptance events; all
other state-update and data expressions are unchanged. This is a source-level
inductive argument under A-NR, not a completed full-wrapper RTL proof.

## Concurrency and handshake obligations

| Simultaneous activity | Obligation |
|---|---|
| M and independent C, same bank/different ordinals | Two selections in the same cycle, including independently stalled consumers |
| M and C, different banks/distinct bound ordinals | Preserve both selections; no global single-bank/one-read rule |
| M and C, same ordinal/other bank unbound or absent | Preserve per-bank presence rejection; never borrow another bank's binding |
| M/C plus lookup | Lookup still compares the existing 64 full records without port-busy backpressure |
| M/C plus withdrawal/transition | Withdrawal's exact original full binding and same-fire timing remain unchanged |
| M/C plus admission to a fresh ordinal | Existing records stay stable; new record appears after the edge |
| lookup plus admission or transition | Preserve transition > admission > stored journal > unseen precedence |
| C/F/B/S/O and unrelated bank events | No source/validation port removed or new consumer arbitration introduced |

All wrapper ready, valid, status and observation-valid signals are compared
each cycle. Compare every output payload when valid, not just when fire, and
compare accepted events and state traces. A Valid-only mirror uses its valid
predicate. Inactive M payload bits are excluded only under the already
documented RD1 invalid-payload rule. C.ready is never excluded by C.valid.
Uninitialized data are not forced equal as a shortcut.

Backpressure behavior is reference-relative: a pre-existing selector/stability
failure must be isolated rather than fixed or hidden by ST1 assumptions.
Report any baseline protocol failure separately from differential mismatch.
Do not introduce new gating to make an invariant easier to prove.

The existing withdrawal selects journal presence/data by ordinal without a
layer qualification. ST1 leaves that behavior intact. Mixed-bank bound/unbound
observation tests must first establish the reference behavior; do not promote
the suffix storage relation into a new claim that all inherited cross-bank
withdrawal semantics are functionally closed, or silently repair that path.

## Verification stages, proposed only

1. **Scope and relation gate:** classify A-NR; freeze the reference revision,
   assertions, source hashes, parameter profiles and comparison predicates.
   Resolve any required generic scenario outside D-G before candidate RTL.
2. **Focused stateful differential proof/test:** keep reference S and candidate
   journal view in a bounded harness with actual write/reset/claim equations.
   Independently drive M/C and journal observers. Use symbolic full-width
   values if a formal flow is available; otherwise label finite simulation as
   such. Cover full 36/64 geometry and parameterized suffix widths, not just a
   single-layer production loopback. Matrix cases ST1-01..ST1-28 are mandatory.
3. **Actual generic-wrapper comparison:** compare old and candidate wrappers
   with paired functional storage environments and identical stimulus. Retain
   original assertions, unbound paths and RD1 behavior. Exercise directed
   pack-read/materialization/reconciliation/publication suites plus the
   previously selected 14-suite/57-case baseline as applicable to the pinned
   revision; derive actual counts from reports, never assume them from history.
   The measurement-DUT/full-root comparison is an additional composition gate.
4. **Isolated matched synthesis, only after separate authorization:** both
   sides must include the already required full journal, presence and the
   same M/C/lookup/withdrawal observability. The baseline also contains S;
   the candidate must not replace its backing by an uncharged oracle/proxy.
   Preserve reachable write association and concurrent reads, same fair-v1
   library/constraints and observability. Inspect raw and mapped state,
   combinational/sequential area, setup/hold, fanout, lint and all completion
   markers/hashes. Characterized wrapper screening is an alternative if the
   isolated harness loses relevant timing/loading. Do not infer state removal
   from the declaration alone.
5. **Integration decision:** only complete candidate functional/source/input
   closure can precede a separately authorized complete paired DC. RD2 may
   change suffix read lowering, so ST1 and RD2 savings cannot be added and
   their combination needs a new frozen input. No full DC is launched here.

Future heavy checks belong to isolated versioned remote roots in named tmux
windows, with resource checks and user notification. This plan does not launch
them or occupy the running RD2 job's environment.

## Current checks and remaining gates

Sixteen static source checks pass; source and prior-audit hashes recheck.
A local two-bank/two-ordinal/two-value storage-equation enumeration visits
81 states and 315 transitions and compares 20,736 ready expressions. It
preserves the relation under fresh journal writes, claims and reset, and
finds the expected duplicate-ordinal counterexample when A-NR is removed.
This is a finite abstract check, not RTL simulation/formal coverage or proof
of full FSM reachability. The source induction above addresses arbitrary
suffix bit patterns conditionally; it still needs binding to real RTL.

The reproducible enumeration is in the appendix. Documentation links, matrix
IDs/status, source hashes and git whitespace checks must pass before commit.
All planned RTL/synthesis cases remain NOT_RUN. No mapped-area, timing,
structural-cleanliness, PPA, external-cost or system-benefit result exists.

**Next required decision:** retain ST1 as a conditional generic candidate and
resolve A-NR's required contract scope before an implementation batch. If the
required generic interface includes raw cross-bank bound-ordinal reuse, reject
the simple journal-only variant rather than narrow behavior or add an admission
gate. A collision-preserving backing/fallback is a different design requiring
its own capacity and cost proof; it is not an assumed free solution.

## Appendix: reduced storage-equation check

Run the following Python with no files or remote access. Initial data zeros
represent one choice of unobservable invalid data, not reset initialization
of the real uninitialized arrays. Claims may clear validity without clearing
data. Readers remain independent; C.valid never gates its ready comparison.

```python
from collections import deque

B = N = 2
values = (0, 1)
initial = ((0,) * (B * N), 0, (0,) * N, (None,) * N)

def invariant(st):
    s, q, j, owner = st
    return all(not (q >> (b * N + o) & 1) or
               (owner[o] == b and s[b * N + o] == j[o])
               for b in range(B) for o in range(N))

seen, todo = {initial}, deque([initial])
transitions = ready_comparisons = 0
while todo:
    st = todo.popleft()
    s, q, j, owner = st
    assert invariant(st)
    for m in range(B * N):
        for c in range(B * N):
            if q >> m & 1:
                assert s[m] == j[m % N]
            for live in (False, True):
                for valid in (False, True):
                    for ready in (False, True):
                        for offered in values:
                            old = live and bool(q >> c & 1) and offered == s[c] and ready
                            new = live and bool(q >> c & 1) and offered == j[c % N] and ready
                            assert old == new
                            assert (valid and old) == (valid and new)
                            ready_comparisons += 1
    successors = [(s, q & ~(((1 << N) - 1) << (b * N)), j, owner)
                  for b in range(B)]
    for b in range(B):
        for o in range(N):
            if owner[o] is not None:
                continue
            for value in values:
                ns, nj, no = list(s), list(j), list(owner)
                ns[b * N + o], nj[o], no[o] = value, value, b
                successors.append((tuple(ns), q | 1 << (b * N + o), tuple(nj), tuple(no)))
    successors.append(initial)
    for nxt in successors:
        assert invariant(nxt)
        transitions += 1
        if nxt not in seen:
            seen.add(nxt)
            todo.append(nxt)
assert (len(seen), transitions, ready_comparisons) == (81, 315, 20736)
# Two accepted writes to ordinal 0 in different banks, ignoring old assertion.
s, j = [0, 0, 1, 0], [1, 0]
assert s[0] != j[0]
assert (0 == s[0]) and not (0 == j[0])
print("ST1_ABSTRACT_CHECK_PASS", len(seen), transitions, ready_comparisons)
print("ST1_RAW_ALIAS_COUNTEREXAMPLE_CONFIRMED")
```
