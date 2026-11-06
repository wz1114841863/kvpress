# Compact-table storage realization alternatives — 2026-11-06

## Scope and main finding

This read-only continuation keeps the generic wrapper's capacity, independent
values, logical concurrency, cycles and ready/valid semantics. No production
or testbench RTL, generated input, clock/constraint, library selection or run
is changed. Remote actions read only existing library functional models and
completed RD1/predecessor reports; no EDA tool or RD2 inspection/process/tmux
operation occurs. Evidence summary:
[`dc_compact_storage_realization_options_20261106.json`](dc_compact_storage_realization_options_20261106.json).

**Full-width values do not require the current cost per stored bit.** Large
storage improvement, if achievable under these interfaces, must come from a
cheaper storage realization and its peripherals rather than unsupported value
truncation or capacity deletion. The most concrete next feasibility candidate
is shared word clock gating plus ordinary DFF data storage (WCG1), not another
journal-only removal of the generic banked suffix array.

This is candidate analysis and library/reference inspection, not an accepted
implementation, mapped saving, timing, power, physical/PPA or net-benefit result.

## What stays necessary

The current data allocation is 36 x 64 x (79 + 80) = 366,336 bits, 44.71875
KiB. Two independent opaque 64-bit fields contribute 294,912 bits. Neither
has a proven short representation under the existing producer contracts.

The rejected unconditional ST1 variant would have discarded bank-specific
suffix values on journal aliasing. That is a different issue from choosing
how the same full-capacity data are physically stored. Retain the member and
suffix logical capacity and the exact optional-binding write distinction.
Unbound admission must not overwrite suffix data merely because it writes the
member at the same address. Claim/reset clears presence; these Reg data arrays
are not initialized/erased on every claim.

A generic dictionary cannot discard arbitrary full-width values. With all
values distinct it needs the values plus tags and lookup/fallback state.
Releasing a record earlier can reduce occupancy or switching, but does not
shrink a fixed array without a proven smaller maximum occupancy. Neither is
currently a large unconditional capacity-saving direction.

## New library and mapping evidence

The inspected target DB remains the fair-v1 library, SHA-256
`5167726cbe6bd25db79549fe12b2a3acaea3b96d8b1b72207620ee7196989a6d`.
The companion functional model contains 1,186 modules. The completed RD1
reference report and sampled member/suffix mapped registers show:

| Library cell | Functional port role | Native unit area |
|---|---|---:|
| `EDFQD2BWP12T30P140LVT` | one D, enable E, clock CP, output Q | 3.528 |
| `DFQD2BWP12T30P140LVT` | one D, clock CP, output Q | 2.520 |
| `CKLNQD1BWP12T30P140LVT` | positive-clock gating function, E/TE/CP/Q | not priced by this batch |
| `LHQD1BWP12T30P140LVT` | level-sensitive D/E/Q storage | not priced by this batch |

Functional inspection confirms that the enabled flip-flop already includes
the D-versus-held-Q selection. The large cost is not necessarily a separate
external hold mux repeated in RTL. Existing predecessor attribution found
only about 8,693 area of immediate data-input drivers for the two tables,
mostly buffers; this is an incomplete cone lower bound, not all write-enable
cost and not an upper bound on WR1. Do not assume hundreds of thousands of
independent removable external hold muxes.

Two current RD1 samples are EDFQD2 member-position and suffix-destination
registers (mapped HDL lines 511414 and 604322). This confirms cell type on
sampled actual storage, not a new full per-bit reference-count attribution.
The prior accepted storage attribution remains 182,016 + 184,320 cells and
approximately 1,292,433 area before RD1. The present analysis does not
reassign that rounded family area as an exactly remeasured RD1 value.

## WCG1: share the write hold mechanism per word

Current functional rule for a data bit is an edge-triggered register enable:
on a core-clock rising edge, update D iff its word write-enable is true.
The internal enabled-cell hold selection is paid per bit. An alternative is:

```text
member row enable -> characterized glitch-free clock gate -> 79 ordinary DFFs
suffix row enable -> characterized glitch-free clock gate -> 80 ordinary DFFs
```

Both values remain full width and all row outputs remain combinationally
readable. No read arbitration, extra cycle, journal capacity condition or
new admission ready decision is inherent in this representation. The two
enables must stay separate: suffix enable additionally requires the accepted
binding. A simple starting organization has 36 x 64 x 2 = 4,608 word gates;
buffering, gate sizing and any different grouping need actual accounting.

For the observed same-library D2 cells, a payload-only arithmetic comparison
is:

```text
366,336 * 3.528 = 1,292,433.408
366,336 * 2.520 =   923,166.720
gross difference = 369,266.688 area units before all new gate/peripheral costs
```

That gross difference is 28.571% of the enabled-cell arithmetic and 10.897%
of RD1's accepted top area 3,388,597.345862. **It is not a candidate area
prediction or measured saving.** Subtract clock gates, clock/data buffering,
enable decode and timing-driven resizing; mapping can choose other cells.
Clock gating that leaves all original enabled cells in place can add area,
so a reduction requires actual replacement/sharing, not merely a gated-clock
annotation. Stored information and data-flop count stay unchanged.

WCG1 requires a separate realization gate before implementation:

- Use the actual characterized positive-clock gate, with an explicit test-
  enable tie policy. Never use a bare `clock & enable` expression.
- Prove its low-phase enable capture produces the same accepted rising-edge
  writes as the original enabled DFF for allowed input setup/hold behavior.
  Same-cycle reset/init, optional binding, late-low-phase enable changes and
  arbitrary data/address changes during the high phase need directed checks.
- Keep every read's pre-edge/next-edge semantics, including independently
  driven C.ready with valid low and simultaneous unrelated row accesses.
- Time gate-enable setup/hold, gated clock propagation, pulse widths and all
  output paths under unchanged external 2.0-ns fair-v1 constraints. Do not
  hide gate-enable paths, add false/multicycle exceptions or loosen Route-A.
- Charge all inserted cells and report both root and gated-branch loads.
  Fewer root loads or less clock activity is not proof of fewer leaf clock
  pins, power savings or timing closure.
- Keep the paired compile methodology fixed. A global clock-gating compiler
  option cannot be enabled only for Route-A and then compared against an
  untreated Full-KV result as if the flow were unchanged. Explicit storage-
  local cell realization or any approved paired flow successor must have
  reviewable input/method provenance and complete accounting.

The available functional model supports the required kind of gate, but this
batch does not verify its full DB characterization, price, synthesis mapping
eligibility or a complete clock-gating implementation. No gated clock is
added to production.

## WR1 and the read network: compatible but bounded directions

Explicitly share the bank/ordinal write decode across a word's fields, with
one member write-enable and the additional suffix qualification. Compare
against what DC already shares; preserve presence-mask updates and concurrent
reads. This may save decode/buffering, but cannot remove the enabled-cell
storage floor by itself. The native integrated enable finding lowers the
priority of blind source rewrites as a large area explanation.

RD2 already screens a different representation of the remaining read muxes.
It does not change data-bit cost. Local row/column selection, word/field
organization and physical clustering can still be studied, but their effects
overlap RD2 and must not be added as independent savings without a new joint
comparison. Neither a nicer source Vec nor conversion from Reg(Vec) to Mem
guarantees a memory macro or lower mapped area.

## Asynchronous register file: the larger storage-realization direction

An implementation with cheaper dense storage cells and explicit asynchronous
read circuitry could keep the same cycle-level interface. A concrete storage
specification must preserve the following conservative per-bank logical needs:

| Stored part | Width | Reads after RD1 | Writes |
|---|---:|---:|---:|
| member payload reference | 64 | shared M/S/O plus independent C/F/B: up to 4 | one selected admission |
| member logical position | 15 | S/O and B: up to 2 | same member admission |
| pending suffix | 80 | independent M and C: 2 | same admission only when binding offered |

The existing read-port analysis is conservative and is not a selected macro
port layout. Fields need not pay for ports their consumers do not read.
Global admission accepts one record per cycle; different row reads still
overlap a write and must see the old record until the edge.

A custom or compiled asynchronous RF might reduce storage-cell area while
read ports, decoders, output drivers and routing remain real costs. A phased
shared-master/latch RF is another possible implementation study; replacing
each DFF with a bare transparent latch is not edge-equivalent. Input capture,
write-address/enable capture and read visibility must be designed/proven
together. Latch presence in the library alone is not enough.

This is a separately scoped larger study, not a macro selected here or a free
array proxy. If no suitable asynchronous realization is available under the
fixed contract, large storage savings cannot be promised under that contract.

## Why the available SRAM is not a drop-in replacement

The checked 64 x 64 SRAM model has one address bus A, one data input/output,
write/chip enables and CLK; its output timing is explicitly clock-edge based.
It is a single-port synchronous service, not the required multi-read
combinational RF. Making the Scala declaration a memory does not change that.

- Banking alone does not solve arbitrary same-bank/different-row read demand.
- Replicating storage can add read ports but increases bits and write fanout;
  four full member copies plus two suffix copies would require 1,096,704 bits,
  about 2.994x current data allocation, before peripherals. Narrow field ports
  can change that arithmetic but do not fix synchronous read latency.
- Prefetch/cache or slower serialized access cannot guarantee the current
  continuously evaluated C/F/B ready behavior for arbitrary supplied indices.
- A synchronous SRAM successor would require an explicit latency/handshake
  review, outside the current generic-wrapper-preservation requirement.

The existing 64 x 64 macro therefore supplies a useful inventory fact, not a
compatible selected solution or an area estimate for these tables.

## Smaller alternatives and exclusions

**Reverse journal reuse:** keep the entire generic suffix table and recover
only the journal's suffix fields from the row named by its existing layer and
ordinal. Both are written together on every bound admission; only another
bound admission overwrites suffix data, and it also updates that ordinal's
journal owner/value. Claim and unbound admission do not overwrite suffix data.
This suggests a reverse relation that does not require A-NR:

```text
journalPresent[o] => journalSuffix[o] == suffixTable[journalLayer[o]][o]
```

Unlike ST1's large-table removal, this retains all bank-specific values.
A reduced storage-equation enumeration with two banks/two ordinals/two values
checks 196 states, 1,960 transitions and 448 cross-bank overwrite transitions
without a nonreuse restriction. This is not RTL equivalence; continued writes
after the original assertion fails are structural diagnostics, not newly legal
wrapper coverage. It removes at most 64 x 80 = 5,120 separately declared data
bits, not 184,320. The scalar enabled-cell gross arithmetic is only 18,063.36
area, 0.533% of RD1 top, before potentially expensive extra read muxes.
The current 64-record parallel reconciliation match could require many new
bank selections, so net area may get worse. It is a low-priority candidate.
The member position/reference cannot be reversed in the same way: a later
unbound admission can replace member data without updating the journal.

**Multi-bit flip-flops:** none with multiple distinct `tsmc_dff` storage nodes
were found in the scanned 1,186-module companion functional model. D2/D4
cells still have one scalar D/Q: drive strength is not bits per cell. This
is not an exhaustive DB capability proof; do not assume a usable multi-bit
replacement, change libraries or quote a saving without further evidence.

**Direct enabled-DFF to latch replacement, capacity shrinking, 64-bit hashes,
constant endpoint/generation or unpriced external backing** are not accepted
ways to meet the present semantics.

## Priority and next concrete study

1. **WCG1 feasibility/cost P0:** characterize the actual word enables and
   candidate gate costs, then specify an edge-equivalence and isolated mapping
   screen using the same library and actual 79/80-bit enable groups. This is
   the most concrete direction for lowering per-bit cost with the current
   interfaces; it is not authorized RTL or a launched experiment here.
2. **WR1 and RD2:** retain decode/read-network opportunities as separately
   measured candidates, without assuming either removes the stored bits.
3. **Asynchronous RF realization:** if a substantially larger storage saving
   is still required, establish a real port/latency/cost option. Do not substitute
   the available synchronous SRAM or a free proxy.
4. Keep reverse journal reuse and multi-bit-cell availability below these
   priorities until their read/mapping costs and actual availability justify work.

The practical conclusion is not that 64-bit metadata makes Route-A
unimplementable. It is that information representation, access circuitry and
the physical storage cell are different optimization axes. At the current
generic interface, the latter two are the remaining credible directions.

## Reproduce the reduced reverse-suffix storage check

This checks only the mirrored write equations. Bank claims/unbound writes do
not modify suffix data; reset invalidates journal visibility. It intentionally
allows structural overwrites without treating post-assertion histories as
newly legal wrapper operation. It does not implement a candidate RF or RTL.

```python
from collections import deque

B = N = 2
initial = ((0,) * (B * N), (0,) * N, (-1,) * N)
seen, todo = {initial}, deque([initial])
transitions = overwrites = 0
while todo:
    s, j, owner = todo.popleft()
    assert all(owner[o] < 0 or j[o] == s[owner[o] * N + o] for o in range(N))
    successors = [(s, j, (-1,) * N), (s, j, owner)]
    for b in range(B):
        for o in range(N):
            for value in (0, 1):
                ns, nj, no = list(s), list(j), list(owner)
                ns[b * N + o] = nj[o] = value
                no[o] = b
                successors.append((tuple(ns), tuple(nj), tuple(no)))
                overwrites += owner[o] >= 0 and owner[o] != b
    for nxt in successors:
        ns, nj, no = nxt
        assert all(no[o] < 0 or nj[o] == ns[no[o] * N + o] for o in range(N))
        transitions += 1
        if nxt not in seen:
            seen.add(nxt)
            todo.append(nxt)
assert (len(seen), transitions, overwrites) == (196, 1960, 448)
print("REVERSE_SUFFIX_ABSTRACT_CHECK_PASS", len(seen), transitions, overwrites)
```
